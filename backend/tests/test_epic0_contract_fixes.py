import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import CurrentUser, get_current_user
from app.auth.security import hash_password, hash_token_sha256
from app.core import Base, get_db
from app.main import app
from app.models import Channel, Membership, RefreshToken, Role, User, Workspace
from tests.async_session_adapter import AsyncSessionAdapter


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        yield session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield AsyncSessionAdapter(db_session)

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# =====================================================================
# S6-01: GET /workspaces
# Done when: Returns workspaces the caller owns or has at least one channel
# membership in; test covers an owner, a channel-member-only user, and an
# unrelated user (empty result).
# =====================================================================

def test_s6_01_get_workspaces_access_and_isolation(client: TestClient, db_session: Session) -> None:
    # Setup users
    owner = User(id=uuid.uuid4(), email="owner@test.com", password_hash=hash_password("pw123456"))
    member_only = User(id=uuid.uuid4(), email="member@test.com", password_hash=hash_password("pw123456"))
    unrelated = User(id=uuid.uuid4(), email="unrelated@test.com", password_hash=hash_password("pw123456"))
    db_session.add_all([owner, member_only, unrelated])

    # Workspace owned by owner
    ws = Workspace(id=uuid.uuid4(), name="Engineering", owner_id=owner.id)
    ch_general = Channel(id=uuid.uuid4(), workspace_id=ws.id, name="general")
    ch_private = Channel(id=uuid.uuid4(), workspace_id=ws.id, name="secret")
    db_session.add_all([ws, ch_general, ch_private])

    # Memberships:
    # owner is in general
    # member_only is only in secret channel
    # unrelated has no memberships
    db_session.add_all([
        Membership(id=uuid.uuid4(), user_id=owner.id, channel_id=ch_general.id, role=Role.OWNER.value),
        Membership(id=uuid.uuid4(), user_id=member_only.id, channel_id=ch_private.id, role=Role.MEMBER.value),
    ])
    db_session.commit()

    # 1. Owner sees the workspace
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=owner.id)
    resp_owner = client.get("/workspaces")
    assert resp_owner.status_code == 200
    workspaces = resp_owner.json()
    assert len(workspaces) == 1
    assert workspaces[0]["id"] == str(ws.id)

    # 2. Channel-member-only user sees the workspace
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=member_only.id)
    resp_member = client.get("/workspaces")
    assert resp_member.status_code == 200
    workspaces_member = resp_member.json()
    assert len(workspaces_member) == 1
    assert workspaces_member[0]["id"] == str(ws.id)

    # 3. Unrelated user gets an empty list
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=unrelated.id)
    resp_unrelated = client.get("/workspaces")
    assert resp_unrelated.status_code == 200
    assert resp_unrelated.json() == []


# =====================================================================
# S6-02: GET /workspaces/{workspace_id}
# Done when: Uses a shared access-check (owner or member of any channel in the
# workspace) so it can never drift from S6-01's logic; documented in API.md with
# the same 403/404 decision as S2-07; test covers access and denial.
# =====================================================================

def test_s6_02_get_workspace_by_id_access_and_denial(client: TestClient, db_session: Session) -> None:
    owner = User(id=uuid.uuid4(), email="ws_owner@test.com", password_hash=hash_password("pw123456"))
    member_only = User(id=uuid.uuid4(), email="ws_member@test.com", password_hash=hash_password("pw123456"))
    unrelated = User(id=uuid.uuid4(), email="ws_unrelated@test.com", password_hash=hash_password("pw123456"))
    db_session.add_all([owner, member_only, unrelated])

    ws = Workspace(id=uuid.uuid4(), name="Platform", owner_id=owner.id)
    ch = Channel(id=uuid.uuid4(), workspace_id=ws.id, name="devs")
    db_session.add_all([ws, ch])

    db_session.add_all([
        Membership(id=uuid.uuid4(), user_id=owner.id, channel_id=ch.id, role=Role.OWNER.value),
        Membership(id=uuid.uuid4(), user_id=member_only.id, channel_id=ch.id, role=Role.MEMBER.value),
    ])
    db_session.commit()

    # Owner can access
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=owner.id)
    resp = client.get(f"/workspaces/{ws.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(ws.id)
    assert resp.json()["name"] == "Platform"

    # Member can access
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=member_only.id)
    resp = client.get(f"/workspaces/{ws.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == str(ws.id)

    # Unrelated user receives 404 (anti-reconnaissance per S2-07 decision)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=unrelated.id)
    resp = client.get(f"/workspaces/{ws.id}")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"

    # Non-existent workspace returns 404
    random_id = uuid.uuid4()
    resp = client.get(f"/workspaces/{random_id}")
    assert resp.status_code == 404


# =====================================================================
# S6-03: GET /workspaces/{workspace_id}/channels
# Done when: Lists only the channels within that workspace the caller is a
# member of — not every channel in the workspace, per the isolation rule in
# permissions.md; test confirms a channel the caller isn't a member of never
# appears, even though it belongs to a workspace they can otherwise access.
# =====================================================================

def test_s6_03_get_workspace_channels_isolation(client: TestClient, db_session: Session) -> None:
    user1 = User(id=uuid.uuid4(), email="user1@test.com", password_hash=hash_password("pw123456"))
    user2 = User(id=uuid.uuid4(), email="user2@test.com", password_hash=hash_password("pw123456"))
    unrelated = User(id=uuid.uuid4(), email="unrelated_ch@test.com", password_hash=hash_password("pw123456"))
    db_session.add_all([user1, user2, unrelated])

    ws = Workspace(id=uuid.uuid4(), name="Company", owner_id=user1.id)
    ch_shared = Channel(id=uuid.uuid4(), workspace_id=ws.id, name="shared")
    ch_user1_only = Channel(id=uuid.uuid4(), workspace_id=ws.id, name="user1-private")
    ch_user2_only = Channel(id=uuid.uuid4(), workspace_id=ws.id, name="user2-private")
    db_session.add_all([ws, ch_shared, ch_user1_only, ch_user2_only])

    db_session.add_all([
        Membership(id=uuid.uuid4(), user_id=user1.id, channel_id=ch_shared.id, role=Role.OWNER.value),
        Membership(id=uuid.uuid4(), user_id=user1.id, channel_id=ch_user1_only.id, role=Role.OWNER.value),
        Membership(id=uuid.uuid4(), user_id=user2.id, channel_id=ch_shared.id, role=Role.MEMBER.value),
        Membership(id=uuid.uuid4(), user_id=user2.id, channel_id=ch_user2_only.id, role=Role.MEMBER.value),
    ])
    db_session.commit()

    # User 2 calls GET /workspaces/{id}/channels:
    # Should see 'shared' and 'user2-private', but NEVER 'user1-private'
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user2.id)
    resp = client.get(f"/workspaces/{ws.id}/channels")
    assert resp.status_code == 200
    channels = resp.json()
    channel_names = [c["name"] for c in channels]
    assert "shared" in channel_names
    assert "user2-private" in channel_names
    assert "user1-private" not in channel_names

    # User 1 calls GET /workspaces/{id}/channels:
    # Should see 'shared' and 'user1-private', but NEVER 'user2-private'
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user1.id)
    resp1 = client.get(f"/workspaces/{ws.id}/channels")
    assert resp1.status_code == 200
    channels1 = resp1.json()
    channel1_names = [c["name"] for c in channels1]
    assert "shared" in channel1_names
    assert "user1-private" in channel1_names
    assert "user2-private" not in channel1_names

    # Unrelated user receives 404 (anti-reconnaissance)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=unrelated.id)
    resp_unrel = client.get(f"/workspaces/{ws.id}/channels")
    assert resp_unrel.status_code == 404


# =====================================================================
# S6-04: Add refresh_token to POST /auth/login's response
# Done when: API.md's login response shape updated to include it; test confirms
# the returned refresh token is valid at /auth/refresh.
# =====================================================================

def test_s6_04_login_returns_refresh_token_valid_at_refresh(client: TestClient) -> None:
    # 1. Register a user
    client.post(
        "/auth/register",
        json={"email": "s604@example.com", "password": "securePassword123!"},
    )

    # 2. Login
    login_resp = client.post(
        "/auth/login",
        json={"email": "s604@example.com", "password": "securePassword123!"},
    )
    assert login_resp.status_code == 200
    login_body = login_resp.json()

    # Must contain both access_token and refresh_token in response body
    assert "access_token" in login_body
    assert "refresh_token" in login_body
    refresh_token = login_body["refresh_token"]
    assert refresh_token is not None and len(refresh_token) > 20

    # 3. Use returned refresh_token directly in JSON body at POST /auth/refresh
    refresh_resp = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    refresh_body = refresh_resp.json()
    assert "access_token" in refresh_body
    assert "refresh_token" in refresh_body
    # Refresh token must be rotated
    assert refresh_body["refresh_token"] != login_body["refresh_token"]

    # Verify access_token works on protected route
    me_resp = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {refresh_body['access_token']}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["user"]["email"] == "s604@example.com"


# =====================================================================
# S6-05: Add POST /auth/logout
# Done when: Revokes the caller's refresh token (revoked_at set); documented in
# API.md; test confirms a revoked token is rejected by /auth/refresh afterward,
# not just deleted client-side.
# =====================================================================

def test_s6_05_logout_revokes_token_server_side(client: TestClient, db_session: Session) -> None:
    client.post(
        "/auth/register",
        json={"email": "s605@example.com", "password": "securePassword123!"},
    )
    login_resp = client.post(
        "/auth/login",
        json={"email": "s605@example.com", "password": "securePassword123!"},
    )
    refresh_token = login_resp.json()["refresh_token"]

    # Call /auth/logout with the refresh token in JSON body
    logout_resp = client.post(
        "/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_resp.status_code == 204

    # Verify server-side that token in DB has revoked_at set
    token_hash = hash_token_sha256(refresh_token)
    record = db_session.query(RefreshToken).filter_by(token_hash=token_hash).first()
    assert record is not None
    assert record.revoked_at is not None

    # Subsequent refresh attempt with this revoked token MUST be rejected
    refresh_resp = client.post(
        "/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 401
    assert refresh_resp.json()["error"]["code"] == "UNAUTHORIZED"
