from collections.abc import Generator
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import CurrentUser, DEV_USER_ID, get_current_user
from app.bot import embed_question
from app.bot.llm import LLMServiceError, LLMTimeoutError
from app.db import Base, get_db
from app.main import app
from app.models import Channel, Chunk, File, Membership, Role, User, Workspace


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


def test_citation_page_matches_source_chunk_metadata(client: TestClient) -> None:
    """S4-06: Asserts returned citation page matches the chunk's stored DB metadata."""
    with client.app.state.test_session_factory() as session:
        user = User(id=DEV_USER_ID, email="user@example.com", password_hash="hash")
        session.add(user)
        workspace = Workspace(id=uuid4(), name="Engineering", owner_id=user.id)
        channel = Channel(id=uuid4(), workspace_id=workspace.id, name="Specs")
        session.add_all([workspace, channel])
        session.add(Membership(user_id=user.id, channel_id=channel.id, role=Role.MEMBER.value))

        spec_file = File(
            id=uuid4(),
            channel_id=channel.id,
            filename="architecture_spec.pdf",
            storage_path="specs/architecture_spec.pdf",
            uploaded_by=user.id,
            ingestion_status="completed",
        )
        session.add(spec_file)

        chunk_12 = Chunk(
            id=uuid4(),
            file_id=spec_file.id,
            channel_id=channel.id,
            page_number=12,
            section="Database Replication",
            content="Database replication uses Raft consensus algorithm.",
            embedding=embed_question("How is database replication achieved?"),
        )
        session.add(chunk_12)
        session.commit()

        # Capture database record values to assert against
        stored_file_id = str(spec_file.id)
        stored_filename = spec_file.filename
        stored_page = chunk_12.page_number
        channel_id = channel.id

    response = client.post(
        f"/channels/{channel_id}/ask",
        json={"question": "How is database replication achieved?"},
        headers={"Authorization": "Bearer dev-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["insufficient_evidence"] is False
    assert len(body["citations"]) == 1
    citation = body["citations"][0]

    # Explicitly assert citation matches stored database chunk metadata, not LLM prose claim
    assert citation["file_id"] == stored_file_id
    assert citation["file_name"] == stored_filename
    assert citation["page"] == stored_page
    assert citation["page"] == 12


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
    """S4-07: Asking a question in a channel with zero files returns insufficient_evidence: True."""
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


def test_channel_with_only_pending_and_failed_files_returns_insufficient_evidence(
    client: TestClient,
) -> None:
    """S4-07: Channel where no file is completed (only pending/failed) returns insufficient_evidence: True."""
    with client.app.state.test_session_factory() as session:
        user = User(id=DEV_USER_ID, email="worker@example.com", password_hash="hash")
        session.add(user)
        workspace = Workspace(id=uuid4(), name="Processing", owner_id=user.id)
        channel = Channel(id=uuid4(), workspace_id=workspace.id, name="Ingestion Queue")
        session.add_all([workspace, channel])
        session.add(Membership(user_id=user.id, channel_id=channel.id, role=Role.MEMBER.value))

        pending_file = File(
            id=uuid4(),
            channel_id=channel.id,
            filename="pending_doc.pdf",
            storage_path="pending.pdf",
            uploaded_by=user.id,
            ingestion_status="pending",
        )
        failed_file = File(
            id=uuid4(),
            channel_id=channel.id,
            filename="corrupt_doc.pdf",
            storage_path="failed.pdf",
            uploaded_by=user.id,
            ingestion_status="failed",
        )
        session.add_all([pending_file, failed_file])

        # Even if chunks exist for uncompleted files, they must not be retrieved
        session.add(
            Chunk(
                id=uuid4(),
                file_id=pending_file.id,
                channel_id=channel.id,
                page_number=1,
                section="Draft",
                content="This is draft content not yet completed.",
                embedding=embed_question("What is in the draft?"),
            )
        )
        session.commit()
        channel_id = channel.id

    response = client.post(
        f"/channels/{channel_id}/ask",
        json={"question": "What is in the draft?"},
        headers={"Authorization": "Bearer dev-token"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Insufficient evidence in this channel to answer the question.",
        "citations": [],
        "insufficient_evidence": True,
    }


def test_channel_with_mixed_files_only_cites_completed_files(client: TestClient) -> None:
    """S4-07: In a channel with completed and pending/failed files, only completed files are retrieved."""
    with client.app.state.test_session_factory() as session:
        user = User(id=DEV_USER_ID, email="mix@example.com", password_hash="hash")
        session.add(user)
        workspace = Workspace(id=uuid4(), name="Mixed", owner_id=user.id)
        channel = Channel(id=uuid4(), workspace_id=workspace.id, name="General")
        session.add_all([workspace, channel])
        session.add(Membership(user_id=user.id, channel_id=channel.id, role=Role.OWNER.value))

        completed_file = File(
            id=uuid4(),
            channel_id=channel.id,
            filename="approved_guide.pdf",
            storage_path="approved.pdf",
            uploaded_by=user.id,
            ingestion_status="completed",
        )
        failed_file = File(
            id=uuid4(),
            channel_id=channel.id,
            filename="broken_guide.pdf",
            storage_path="broken.pdf",
            uploaded_by=user.id,
            ingestion_status="failed",
        )
        session.add_all([completed_file, failed_file])

        completed_chunk = Chunk(
            id=uuid4(),
            file_id=completed_file.id,
            channel_id=channel.id,
            page_number=7,
            section="Deployment",
            content="Deploy to production using blue-green strategy.",
            embedding=embed_question("How do we deploy to production?"),
        )
        failed_chunk = Chunk(
            id=uuid4(),
            file_id=failed_file.id,
            channel_id=channel.id,
            page_number=3,
            section="Broken",
            content="Deploy using canary strategy.",
            embedding=embed_question("How do we deploy to production?"),
        )
        session.add_all([completed_chunk, failed_chunk])
        session.commit()

        stored_file_id = str(completed_file.id)
        channel_id = channel.id

    response = client.post(
        f"/channels/{channel_id}/ask",
        json={"question": "How do we deploy to production?"},
        headers={"Authorization": "Bearer dev-token"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["insufficient_evidence"] is False
    assert len(body["citations"]) == 1
    assert body["citations"][0]["file_id"] == stored_file_id
    assert body["citations"][0]["file_name"] == "approved_guide.pdf"
    assert body["citations"][0]["page"] == 7


def test_llm_timeout_returns_documented_error_shape(client: TestClient) -> None:
    """S4-08: LLM timeout returns a documented error shape matching API.md."""
    with client.app.state.test_session_factory() as session:
        channel_id = create_channel(session)

    with patch("app.bot.routes.generate_answer", side_effect=LLMTimeoutError("Claude API request timed out.")):
        response = client.post(
            f"/channels/{channel_id}/ask",
            json={"question": "When is the release date?"},
            headers={"Authorization": "Bearer dev-token"},
        )

    assert response.status_code == 504
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "GATEWAY_TIMEOUT"
    assert "timed out" in body["error"]["message"].lower()
    assert UUID(body["error"]["request_id"])  # Validates request_id is a UUID string


def test_llm_error_returns_documented_error_shape(client: TestClient) -> None:
    """S4-08: LLM error returns a documented error shape matching API.md."""
    with client.app.state.test_session_factory() as session:
        channel_id = create_channel(session)

    with patch("app.bot.routes.generate_answer", side_effect=LLMServiceError("Claude API returned status 500.")):
        response = client.post(
            f"/channels/{channel_id}/ask",
            json={"question": "When is the release date?"},
            headers={"Authorization": "Bearer dev-token"},
        )

    assert response.status_code == 502
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "BAD_GATEWAY"
    assert "status 500" in body["error"]["message"]
    assert UUID(body["error"]["request_id"])  # Validates request_id is a UUID string


def test_question_with_no_relevant_materials_returns_insufficient_evidence(client: TestClient) -> None:
    """S4-04: Question with no relevant materials (below similarity threshold) returns insufficient_evidence."""
    with client.app.state.test_session_factory() as session:
        user = User(id=DEV_USER_ID, email="irrelevant@example.com", password_hash="hash")
        session.add(user)
        workspace = Workspace(id=uuid4(), name="Space", owner_id=user.id)
        channel = Channel(id=uuid4(), workspace_id=workspace.id, name="General")
        session.add_all([workspace, channel])
        session.add(Membership(user_id=user.id, channel_id=channel.id, role=Role.MEMBER.value))

        file = File(
            id=uuid4(),
            channel_id=channel.id,
            filename="irrelevant.pdf",
            storage_path="irrelevant.pdf",
            uploaded_by=user.id,
            ingestion_status="completed",
        )
        session.add(file)

        # Chunk with orthogonal embedding resulting in 0.0 cosine similarity
        orthogonal_embedding = [0.0] * 384
        orthogonal_embedding[0] = 1.0
        session.add(
            Chunk(
                id=uuid4(),
                file_id=file.id,
                channel_id=channel.id,
                page_number=1,
                section="Irrelevant",
                content="Irrelevant topic text.",
                embedding=orthogonal_embedding,
            )
        )
        session.commit()
        channel_id = channel.id

    with patch("app.bot.routes.search_channel_chunks", return_value=[]):
        response = client.post(
            f"/channels/{channel_id}/ask",
            json={"question": "What is the completely unrelated topic?"},
            headers={"Authorization": "Bearer dev-token"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Insufficient evidence in this channel to answer the question.",
        "citations": [],
        "insufficient_evidence": True,
    }


@pytest.mark.parametrize("role", [Role.OWNER, Role.ADMIN, Role.MEMBER, Role.READ_ONLY])
def test_ask_endpoint_allows_all_four_channel_roles(client: TestClient, role: Role) -> None:
    """S4-10: Confirms owner, admin, member, and read_only are all authorized to ask."""
    user_id = uuid4()
    with client.app.state.test_session_factory() as session:
        user = User(id=user_id, email=f"user-{role.value}@example.com", password_hash="hash")
        session.add(user)
        workspace = Workspace(id=uuid4(), name="Engineering", owner_id=user_id)
        channel = Channel(id=uuid4(), workspace_id=workspace.id, name=f"Channel-{role.value}")
        session.add_all([workspace, channel])
        session.add(Membership(user_id=user_id, channel_id=channel.id, role=role.value))
        session.commit()
        channel_id = channel.id

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_id)
    response = client.post(
        f"/channels/{channel_id}/ask",
        json={"question": "What is our process?"},
        headers={"Authorization": "Bearer dev-token"},
    )
    assert response.status_code == 200


def test_ask_endpoint_denies_non_member(client: TestClient) -> None:
    """S4-10: Confirms a non-member is denied access to the ask endpoint."""
    user_id = uuid4()
    with client.app.state.test_session_factory() as session:
        creator_id = uuid4()
        creator = User(id=creator_id, email="creator@example.com", password_hash="hash")
        session.add(creator)
        workspace = Workspace(id=uuid4(), name="Engineering", owner_id=creator_id)
        channel = Channel(id=uuid4(), workspace_id=workspace.id, name="Secret Channel")
        session.add_all([workspace, channel])
        session.add(Membership(user_id=creator_id, channel_id=channel.id, role=Role.OWNER.value))
        session.commit()
        channel_id = channel.id

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=user_id)
    response = client.post(
        f"/channels/{channel_id}/ask",
        json={"question": "Can I see secret data?"},
        headers={"Authorization": "Bearer dev-token"},
    )
    assert response.status_code == 404

