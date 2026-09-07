from collections.abc import Generator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import CurrentUser, DEV_USER_ID, get_current_user
from app.core import Base, get_db
from app.main import app
from tests.async_session_adapter import AsyncSessionAdapter



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
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_create_workspace_sets_authenticated_owner(client: TestClient) -> None:
    response = client.post(
        "/workspaces",
        json={"name": "Engineering"},
        headers={"Authorization": "Bearer dev-token"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Engineering"
    assert UUID(body["owner_id"]) == DEV_USER_ID
    assert UUID(body["id"])
    assert body["created_at"].endswith("+00:00")


def test_create_workspace_requires_authentication(client: TestClient) -> None:
    app.dependency_overrides.clear()
    response = client.post("/workspaces", json={"name": "Engineering"})

    assert response.status_code == 401
