from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import CurrentUser, get_current_user
from app.core import Base
from app.core.db import get_db
from app.main import app
from app.models import Membership, User
from tests.async_session_adapter import AsyncSessionAdapter

DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield AsyncSessionAdapter(session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=DEV_USER_ID)
    app.state.test_session_factory = session_factory
    app.state.test_engine = engine

    with session_factory() as session:
        user = User(
            id=DEV_USER_ID,
            username="dev_owner",
            email="owner@example.com",
            password_hash="hash",
        )
        session.add(user)
        session.commit()

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ==============================================================================
# S11-12: Role Authorization Matrix for Threads & Notifications
# ==============================================================================


@pytest.mark.parametrize(
    "role,can_view_thread,can_reply",
    [
        ("owner", True, True),
        ("admin", True, True),
        ("member", True, True),
        ("read_only", True, False),
    ],
)
def test_s11_12_role_matrix_threads(
    client: TestClient, role: str, can_view_thread: bool, can_reply: bool
) -> None:
    session_factory = app.state.test_session_factory
    user_id = uuid4()

    workspace_res = client.post("/workspaces", json={"name": f"WS-{role}"})
    workspace_id = workspace_res.json()["id"]

    channel_res = client.post(
        f"/workspaces/{workspace_id}/channels", json={"name": f"ch-{role}"}
    )
    channel_id = channel_res.json()["id"]

    with session_factory() as session:
        u = User(
            id=user_id,
            username=f"user_{role}_{user_id.hex[:6]}",
            email=f"{role}_{user_id.hex[:6]}@example.com",
            password_hash="hash",
        )
        session.add(u)
        session.add(
            Membership(
                user_id=user_id, channel_id=UUID(channel_id), role=role
            )
        )
        session.commit()

    # Owner creates root message
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=DEV_USER_ID)
    root_res = client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "Root topic for role testing"},
    )
    root_id = root_res.json()["id"]

    # Now act as the test role
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_id)

    # 1. View thread
    view_res = client.get(f"/channels/{channel_id}/messages/{root_id}/thread")
    if can_view_thread:
        assert view_res.status_code == 200
    else:
        assert view_res.status_code in (403, 404)

    # 2. Reply to thread
    reply_res = client.post(
        f"/channels/{channel_id}/messages",
        json={
            "content": f"Reply from {role}",
            "parent_message_id": root_id,
        },
    )
    if can_reply:
        assert reply_res.status_code == 201
    else:
        assert reply_res.status_code == 403


def test_s11_12_non_member_disclosure_denial(client: TestClient) -> None:
    session_factory = app.state.test_session_factory
    outsider_id = uuid4()

    workspace_res = client.post("/workspaces", json={"name": "Private WS"})
    workspace_id = workspace_res.json()["id"]

    channel_res = client.post(
        f"/workspaces/{workspace_id}/channels", json={"name": "private-ch"}
    )
    channel_id = channel_res.json()["id"]

    with session_factory() as session:
        outsider = User(
            id=outsider_id,
            username="outsider",
            email="outsider@example.com",
            password_hash="hash",
        )
        session.add(outsider)
        session.commit()

    # Owner creates root message
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=DEV_USER_ID)
    root_res = client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "Secret root message"},
    )
    root_id = root_res.json()["id"]

    # Outsider attempts to view thread -> 404 (disclosure safe)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=outsider_id
    )
    get_res = client.get(f"/channels/{channel_id}/messages/{root_id}/thread")
    assert get_res.status_code == 404

    # Outsider attempts to post reply -> 404
    reply_res = client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "Sneak attempt", "parent_message_id": root_id},
    )
    assert reply_res.status_code == 404


# ==============================================================================
# S11-13: Cross-User Isolation Leak Test
# ==============================================================================


def test_s11_13_cross_user_isolation_leak(client: TestClient) -> None:
    session_factory = app.state.test_session_factory

    user_a = uuid4()
    user_b = uuid4()
    user_c = uuid4()

    workspace_res = client.post("/workspaces", json={"name": "Tenant WS"})
    workspace_id = workspace_res.json()["id"]

    channel_res = client.post(
        f"/workspaces/{workspace_id}/channels", json={"name": "collab-ch"}
    )
    channel_id = UUID(channel_res.json()["id"])

    with session_factory() as session:
        ua = User(id=user_a, username="user_a", email="a@example.com", password_hash="h")
        ub = User(id=user_b, username="user_b", email="b@example.com", password_hash="h")
        uc = User(id=user_c, username="user_c", email="c@example.com", password_hash="h")
        session.add_all([ua, ub, uc])
        session.add_all([
            Membership(user_id=user_a, channel_id=channel_id, role="member"),
            Membership(user_id=user_b, channel_id=channel_id, role="member"),
            Membership(user_id=user_c, channel_id=channel_id, role="member"),
        ])
        session.commit()

    # User A posts a message mentioning User B only
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_a)
    client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "Confidential task for @user_b"},
    )

    # 1. User B should have 1 unread notification
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_b)
    b_unread = client.get("/notifications/unread-count").json()["unread_count"]
    b_inbox = client.get("/notifications").json()["items"]
    assert b_unread == 1
    assert len(b_inbox) == 1
    assert b_inbox[0]["user_id"] == str(user_b)
    b_notif_id = b_inbox[0]["id"]

    # 2. User C should have 0 notifications (no leak)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_c)
    c_unread = client.get("/notifications/unread-count").json()["unread_count"]
    c_inbox = client.get("/notifications").json()["items"]
    assert c_unread == 0
    assert len(c_inbox) == 0

    # 3. User C cannot mark User B's notification as read (returns 404)
    c_mark_res = client.patch(f"/notifications/{b_notif_id}/read")
    assert c_mark_res.status_code == 404

    # 4. User B's notification status must remain unread
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_b)
    b_unread_after = client.get("/notifications/unread-count").json()["unread_count"]
    assert b_unread_after == 1
