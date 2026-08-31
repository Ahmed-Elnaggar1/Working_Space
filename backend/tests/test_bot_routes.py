from collections.abc import Generator
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import CurrentUser, DEV_USER_ID, get_current_user
from app.bot import embed_question
from app.db import Base, get_db
from app.main import app
from app.models import Channel, Chunk, File, Membership, Role, User, Workspace


import pytest


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    monkeypatch.setenv("LLM_PROVIDER", "placeholder")
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


def create_channel(session: Session) -> UUID:
    session.add(User(id=DEV_USER_ID, email="owner@example.com", password_hash="hash"))
    workspace = Workspace(id=uuid4(), name="Engineering", owner_id=DEV_USER_ID)
    channel = Channel(id=uuid4(), workspace_id=workspace.id, name="Backend")
    session.add_all([workspace, channel])
    session.add(Membership(user_id=DEV_USER_ID, channel_id=channel.id, role=Role.OWNER.value))
    file = File(
        id=uuid4(),
        channel_id=channel.id,
        filename="plan.pdf",
        storage_path="plan.pdf",
        uploaded_by=DEV_USER_ID,
        ingestion_status="completed",
    )
    session.add(file)
    session.add(
        Chunk(
            id=uuid4(),
            file_id=file.id,
            channel_id=channel.id,
            page_number=4,
            section="Release",
            content="The release date is 2027-01-15.",
            embedding=embed_question("When is the release date?"),
        )
    )
    session.commit()
    return channel.id


def test_member_can_ask_and_receives_citation(client: TestClient) -> None:
    with client.app.state.test_session_factory() as session:
        channel_id = create_channel(session)

    response = client.post(
        f"/channels/{channel_id}/ask",
        json={"question": "When is the release date?"},
        headers={"Authorization": "Bearer dev-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["insufficient_evidence"] is False
    assert body["citations"] == [
        {"file_id": body["citations"][0]["file_id"], "file_name": "plan.pdf", "page": 4}
    ]


def test_non_member_cannot_ask(client: TestClient) -> None:
    with client.app.state.test_session_factory() as session:
        channel_id = create_channel(session)

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=uuid4())
    response = client.post(
        f"/channels/{channel_id}/ask",
        json={"question": "When is the release date?"},
        headers={"Authorization": "Bearer dev-token"},
    )

    assert response.status_code == 404


def test_empty_channel_returns_insufficient_evidence(client: TestClient) -> None:
    with client.app.state.test_session_factory() as session:
        session.add(User(id=DEV_USER_ID, email="empty@example.com", password_hash="hash"))
        workspace = Workspace(id=uuid4(), name="Empty", owner_id=DEV_USER_ID)
        channel = Channel(id=uuid4(), workspace_id=workspace.id, name="No Files")
        session.add_all([workspace, channel])
        session.add(Membership(user_id=DEV_USER_ID, channel_id=channel.id, role=Role.OWNER.value))
        session.commit()
        channel_id = channel.id

    response = client.post(
        f"/channels/{channel_id}/ask",
        json={"question": "Anything here?"},
        headers={"Authorization": "Bearer dev-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Insufficient evidence in this channel to answer the question.",
        "citations": [],
        "insufficient_evidence": True,
    }
