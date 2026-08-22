from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import CurrentUser, DEV_USER_ID, get_current_user
from app.db import Base, get_db
from app.main import app
from app.models import Membership, Role


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
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=DEV_USER_ID)
    app.state.test_session_factory = session_factory
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_workspace(client: TestClient) -> str:
    response = client.post(
        "/workspaces",
        json={"name": "Engineering"},
        headers={"Authorization": "Bearer dev-token"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_create_channel_creates_owner_membership(client: TestClient) -> None:
    workspace_id = create_workspace(client)

    response = client.post(
        f"/workspaces/{workspace_id}/channels",
        json={"name": "Backend"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Backend"
    assert body["workspace_id"] == workspace_id

    with app.state.test_session_factory() as session:
        membership = session.query(Membership).one()
        assert membership.user_id == DEV_USER_ID
        assert membership.channel_id == UUID(body["id"])
        assert membership.role == Role.OWNER.value


def test_duplicate_channel_name_returns_conflict(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    payload = {"name": "Backend"}

    first = client.post(f"/workspaces/{workspace_id}/channels", json=payload)
    second = client.post(f"/workspaces/{workspace_id}/channels", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


def test_non_owner_cannot_create_channel(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    other_user_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=other_user_id)

    response = client.post(
        f"/workspaces/{workspace_id}/channels",
        json={"name": "Backend"},
    )

    assert response.status_code == 403


def test_member_can_get_channel_but_non_member_cannot(client: TestClient) -> None:
    workspace_id = create_workspace(client)
    created = client.post(
        f"/workspaces/{workspace_id}/channels",
        json={"name": "Backend"},
    )
    channel_id = created.json()["id"]

    assert client.get(f"/channels/{channel_id}").status_code == 200

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=uuid4())
    response = client.get(f"/channels/{channel_id}")

    assert response.status_code == 404


def test_unknown_channel_returns_not_found(client: TestClient) -> None:
    response = client.get(f"/channels/{uuid4()}")

    assert response.status_code == 404
