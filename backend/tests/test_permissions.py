from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi import APIRouter, Depends

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import CurrentUser, get_current_user
from app.db import Base, get_db
from app.main import app
from app.models import Channel, Membership, Role, User, Workspace
from app.permissions import require_role

# Create a dummy router to test the dependency integration
permissions_dummy_router = APIRouter(prefix="/test-permissions-auth")


@permissions_dummy_router.get(
    "/channels/{channel_id}/view",
    dependencies=[Depends(require_role("view_channel"))],
)
def dummy_view_channel_endpoint(channel_id: UUID):
    return {"status": "authorized"}


@permissions_dummy_router.post(
    "/channels/{channel_id}/send-message",
    dependencies=[Depends(require_role("send_messages"))],
)
def dummy_send_message_endpoint(channel_id: UUID):
    return {"status": "authorized"}


@permissions_dummy_router.delete(
    "/channels/{channel_id}/delete",
    dependencies=[Depends(require_role("delete_channel"))],
)
def dummy_delete_channel_endpoint(channel_id: UUID):
    return {"status": "authorized"}


@pytest.fixture(scope="module")
def setup_app_router():
    # Register test router on main app
    app.include_router(permissions_dummy_router)
    yield
    # No clean way to remove router in FastAPI, but dependency_overrides.clear() will clear other mocks



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
def client(db_session: Session, setup_app_router) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_require_role_channel_not_found(client: TestClient, db_session: Session):
    # Setup authenticated user
    user_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_id)

    non_existent_channel_id = uuid4()
    response = client.get(
        f"/test-permissions-auth/channels/{non_existent_channel_id}/view",
        headers={"Authorization": "Bearer dev-token"},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "Channel not found"


def test_require_role_non_member(client: TestClient, db_session: Session):
    user_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_id)

    # Create user, workspace, and channel, but no membership
    creator = User(email="creator@example.com", password_hash="dummy")
    db_session.add(creator)
    db_session.flush()

    workspace = Workspace(name="WS", owner_id=creator.id)
    db_session.add(workspace)
    db_session.flush()

    channel = Channel(workspace_id=workspace.id, name="General")
    db_session.add(channel)
    db_session.commit()

    response = client.get(
        f"/test-permissions-auth/channels/{channel.id}/view",
        headers={"Authorization": "Bearer dev-token"},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"


@pytest.mark.parametrize(
    "role, action, expected_status",
    [
        # Read-only role tests
        (Role.READ_ONLY, "view", 200),
        (Role.READ_ONLY, "send-message", 403),
        (Role.READ_ONLY, "delete", 403),
        # Member role tests
        (Role.MEMBER, "view", 200),
        (Role.MEMBER, "send-message", 200),
        (Role.MEMBER, "delete", 403),
        # Admin role tests
        (Role.ADMIN, "view", 200),
        (Role.ADMIN, "send-message", 200),
        (Role.ADMIN, "delete", 403),
        # Owner role tests
        (Role.OWNER, "view", 200),
        (Role.OWNER, "send-message", 200),
        (Role.OWNER, "delete", 200),
    ],
)
def test_role_matrix_enforcement(
    client: TestClient,
    db_session: Session,
    role: Role,
    action: str,
    expected_status: int,
):
    user = User(email=f"user-{role.value}@example.com", password_hash="dummy")
    db_session.add(user)
    db_session.flush()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user.id)

    workspace = Workspace(name="WS", owner_id=user.id)
    db_session.add(workspace)
    db_session.flush()

    channel = Channel(workspace_id=workspace.id, name=f"Channel-{role.value}-{action}")
    db_session.add(channel)
    db_session.flush()

    membership = Membership(user_id=user.id, channel_id=channel.id, role=role.value)
    db_session.add(membership)
    db_session.commit()

    if action == "view":
        response = client.get(f"/test-permissions-auth/channels/{channel.id}/view")
    elif action == "send-message":
        response = client.post(f"/test-permissions-auth/channels/{channel.id}/send-message")
    elif action == "delete":
        response = client.delete(f"/test-permissions-auth/channels/{channel.id}/delete")

    assert response.status_code == expected_status

    if expected_status == 403:
        body = response.json()
        assert body["error"]["code"] == "FORBIDDEN"
