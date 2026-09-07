from collections.abc import Generator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import CurrentUser, DEV_USER_ID, get_current_user
from app.core import Base, get_db
from app.files.storage import storage
from app.main import app
from app.models import Membership, Role, User
from tests.async_session_adapter import AsyncSessionAdapter


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(storage, "endpoint_url", None)
    monkeypatch.setattr(storage, "aws_access_key", None)
    monkeypatch.setattr(storage, "aws_secret_key", None)

    def override_get_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield AsyncSessionAdapter(session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=DEV_USER_ID)
    app.state.test_session_factory = session_factory
    app.state.test_async_session_factory = lambda: AsyncSessionAdapter(session_factory())
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    delattr(app.state, "test_async_session_factory")


def create_workspace_and_channel(client: TestClient, user_id: UUID | None = None) -> tuple[str, str]:
    if user_id is not None:
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_id)

    workspace_response = client.post(
        "/workspaces",
        json={"name": "Engineering"},
        headers={"Authorization": "Bearer dev-token"},
    )
    assert workspace_response.status_code == 201
    workspace_id = workspace_response.json()["id"]

    channel_response = client.post(
        f"/workspaces/{workspace_id}/channels",
        json={"name": "Files"},
    )
    assert channel_response.status_code == 201
    channel_id = channel_response.json()["id"]
    return workspace_id, channel_id


def test_upload_and_list_files_require_channel_membership(client: TestClient) -> None:
    _, channel_id = create_workspace_and_channel(client, DEV_USER_ID)

    response = client.post(
        f"/channels/{channel_id}/files",
        files={"file": ("notes.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["file_name"] == "notes.txt"
    assert body["ingestion_status"] == "pending"
    assert "content" not in body

    list_response = client.get(f"/channels/{channel_id}/files")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    outsider_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=outsider_id)
    list_response = client.get(f"/channels/{channel_id}/files")
    assert list_response.status_code == 404


def test_download_file_validates_channel_membership(client: TestClient) -> None:
    _, channel_id = create_workspace_and_channel(client, DEV_USER_ID)

    upload = client.post(
        f"/channels/{channel_id}/files",
        files={"file": ("report.pdf", b"pdf-bytes-123", "application/pdf")},
    )
    file_id = upload.json()["id"]

    download = client.get(f"/channels/{channel_id}/files/{file_id}/download")
    assert download.status_code == 200
    assert download.content == b"pdf-bytes-123"

    outsider_id = uuid4()
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=outsider_id)
    denied = client.get(f"/channels/{channel_id}/files/{file_id}/download")
    assert denied.status_code == 404


def test_delete_file_permissions_and_storage_cleanup(client: TestClient) -> None:
    _, channel_id = create_workspace_and_channel(client, DEV_USER_ID)

    upload = client.post(
        f"/channels/{channel_id}/files",
        files={"file": ("alpha.txt", b"alpha-data", "text/plain")},
    )
    file_id = upload.json()["id"]

    member_id = uuid4()
    with app.state.test_session_factory() as session:
        session.add(User(id=member_id, email="member@example.com", password_hash="dummy"))
        session.add(Membership(user_id=member_id, channel_id=UUID(channel_id), role=Role.MEMBER.value))
        session.commit()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=member_id)
    response = client.delete(f"/channels/{channel_id}/files/{file_id}")
    assert response.status_code == 403

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=DEV_USER_ID)
    response = client.delete(f"/channels/{channel_id}/files/{file_id}")
    assert response.status_code == 204

    response = client.get(f"/channels/{channel_id}/files")
    assert response.status_code == 200
    assert response.json() == []

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=member_id)
    member_upload = client.post(
        f"/channels/{channel_id}/files",
        files={"file": ("beta.txt", b"beta-data", "text/plain")},
    )
    own_file_id = member_upload.json()["id"]

    member_delete = client.delete(f"/channels/{channel_id}/files/{own_file_id}")
    assert member_delete.status_code == 204

    read_only_id = uuid4()
    with app.state.test_session_factory() as session:
        session.add(User(id=read_only_id, email="readonly@example.com", password_hash="dummy"))
        session.add(Membership(user_id=read_only_id, channel_id=UUID(channel_id), role=Role.READ_ONLY.value))
        session.commit()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=read_only_id)
    denied = client.post(
        f"/channels/{channel_id}/files",
        files={"file": ("gamma.txt", b"gamma-data", "text/plain")},
    )
    assert denied.status_code == 403
