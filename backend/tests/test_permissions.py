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

permissions_dummy_router = APIRouter(prefix="/test-permissions-auth")


MATRIX_ROUTES = {
    "view_channel": ("get", "view-channel"),
    "view_messages": ("get", "view-messages"),
    "send_messages": ("post", "send-messages"),
    "ask_bot": ("post", "ask-bot"),
    "view_files": ("get", "view-files"),
    "upload_files": ("post", "upload-files"),
    "delete_own_file": ("delete", "delete-own-file"),
    "delete_any_file": ("delete", "delete-any-file"),
    "add_remove_members": ("post", "add-remove-members"),
    "change_member_roles": ("patch", "change-member-roles"),
    "rename_channel": ("patch", "rename-channel"),
    "delete_channel": ("delete", "delete-channel"),
    "manage_workspace_owner": ("patch", "manage-workspace-owner"),
}


def matrix_endpoint(channel_id: UUID):
    return {"status": "authorized"}


for action, (method, path_name) in MATRIX_ROUTES.items():
    permissions_dummy_router.add_api_route(
        f"/channels/{{channel_id}}/{path_name}",
        matrix_endpoint,
        methods=[method.upper()],
        dependencies=[Depends(require_role(action))],
    )


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
    assert body["error"]["message"] == "Not Found"


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


ROLE_ACTION_MATRIX = [
    (Role.OWNER, action, action in {
        "view_channel",
        "view_messages",
        "send_messages",
        "ask_bot",
        "view_files",
        "upload_files",
        "delete_own_file",
        "delete_any_file",
        "add_remove_members",
        "change_member_roles",
        "rename_channel",
        "delete_channel",
        "manage_workspace_owner",
    })
    for action in MATRIX_ROUTES
] + [
    (Role.ADMIN, action, action in {
        "view_channel",
        "view_messages",
        "send_messages",
        "ask_bot",
        "view_files",
        "upload_files",
        "delete_own_file",
        "delete_any_file",
        "add_remove_members",
        "change_member_roles",
        "rename_channel",
    })
    for action in MATRIX_ROUTES
] + [
    (Role.MEMBER, action, action in {
        "view_channel",
        "view_messages",
        "send_messages",
        "ask_bot",
        "view_files",
        "upload_files",
        "delete_own_file",
    })
    for action in MATRIX_ROUTES
] + [
    (Role.READ_ONLY, action, action in {
        "view_channel",
        "view_messages",
        "ask_bot",
        "view_files",
    })
    for action in MATRIX_ROUTES
]


@pytest.mark.parametrize("role, action, allowed", ROLE_ACTION_MATRIX)
def test_role_matrix_enforcement(
    client: TestClient,
    db_session: Session,
    role: Role,
    action: str,
    allowed: bool,
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

    method, path_name = MATRIX_ROUTES[action]
    request = getattr(client, method)
    response = request(f"/test-permissions-auth/channels/{channel.id}/{path_name}")

    assert response.status_code == (200 if allowed else 403)

    if not allowed:
        body = response.json()
        assert body["error"]["code"] == "FORBIDDEN"
