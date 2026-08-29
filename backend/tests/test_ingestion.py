from collections.abc import Generator
import io
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import CurrentUser, DEV_USER_ID, get_current_user
from app.db import Base, get_db
from app.main import app
from app.models import Membership, Role, Channel, File, Chunk, User, Workspace
from app.ingestion.parser import parse_file, ParsingError
from app.ingestion.chunker import chunk_parsed_content
from app.ingestion.embeddings import generate_embedding
from app.ingestion.pipeline import run_ingestion_pipeline
from app.files.storage import storage

# Minimal valid PDF bytes for pypdf tests
MINIMAL_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
    b"2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n"
    b"3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/Resources <<\n/Font <<\n/F1 <<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\n>>\n>>\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n>>\nendobj\n"
    b"4 0 obj\n<<\n/Length 44\n>>\nstream\n"
    b"BT\n/F1 12 Tf\n72 712 Td\n(Hello world from page one) Tj\nET\n"
    b"endstream\n"
    b"endobj\n"
    b"xref\n"
    b"0 5\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000058 00000 n \n"
    b"0000000115 00000 n \n"
    b"0000000282 00000 n \n"
    b"trailer\n<<\n/Size 5\n/Root 1 0 R\n>>\n"
    b"startxref\n"
    b"377\n"
    b"%%EOF"
)


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
def mock_storage(monkeypatch):
    stored_files = {}

    def mock_upload_file(key, file_data, content_type="application/octet-stream"):
        stored_files[key] = file_data
        return key

    def mock_download_file(key):
        if key not in stored_files:
            # Raise botocore ClientError to match real behavior
            from botocore.exceptions import ClientError
            raise ClientError({"Error": {"Code": "NoSuchKey", "Message": "Not found"}}, "GetObject")
        return stored_files[key]

    def mock_delete_file(key):
        stored_files.pop(key, None)

    monkeypatch.setattr(storage, "upload_file", mock_upload_file)
    monkeypatch.setattr(storage, "download_file", mock_download_file)
    monkeypatch.setattr(storage, "delete_file", mock_delete_file)
    return stored_files


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=DEV_USER_ID)
    app.state.test_session_factory = lambda: db_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def setup_workspace_and_channel(db: Session, owner_id: UUID) -> tuple[Workspace, Channel]:
    # Setup owner user if not exists
    user = db.get(User, owner_id)
    if not user:
        user = User(id=owner_id, email="owner@example.com", password_hash="dummy")
        db.add(user)
    
    workspace = Workspace(name="Test Workspace", owner_id=owner_id)
    db.add(workspace)
    db.flush()
    
    channel = Channel(workspace_id=workspace.id, name="General")
    db.add(channel)
    db.flush()
    
    membership = Membership(user_id=owner_id, channel_id=channel.id, role=Role.OWNER.value)
    db.add(membership)
    db.commit()
    
    return workspace, channel


# ==================== PARSER TESTS ====================

def test_parse_valid_pdf():
    parsed = parse_file("test.pdf", MINIMAL_PDF_BYTES)
    assert len(parsed) == 1
    assert parsed[0][0] == 1
    assert "Hello world" in parsed[0][1]


def test_parse_corrupt_pdf():
    with pytest.raises(ParsingError) as exc_info:
        parse_file("corrupt.pdf", b"not a pdf at all")
    assert "Invalid file signature" in str(exc_info.value)


def test_parse_plain_text():
    content = b"This is line 1.\nThis is line 2."
    parsed = parse_file("doc.txt", content)
    assert len(parsed) == 1
    assert parsed[0][0] == 1
    assert "This is line 1" in parsed[0][1]


def test_parse_unsupported_type():
    with pytest.raises(ParsingError) as exc_info:
        parse_file("image.png", b"some bytes")
    assert "Unsupported file type" in str(exc_info.value)


# ==================== CHUNKER TESTS ====================

def test_chunker_retains_page_numbers():
    pages = [
        (1, "word " * 400),  # Page 1: 400 words (should split into 2 chunks)
        (2, "another " * 100),  # Page 2: 100 words
    ]
    chunks = chunk_parsed_content(pages, max_words=300, overlap=50)
    
    assert len(chunks) == 3
    
    # Page 1 chunks
    assert chunks[0]["page_number"] == 1
    assert chunks[1]["page_number"] == 1
    
    # Page 2 chunk
    assert chunks[2]["page_number"] == 2


# ==================== EMBEDDINGS TESTS ====================

def test_embeddings_generation_dimension_and_determinism():
    text = "Hello world embedding test"
    emb1 = generate_embedding(text, dimension=1536)
    emb2 = generate_embedding(text, dimension=1536)
    
    assert len(emb1) == 1536
    assert emb1 == emb2  # Determinism
    
    # Check L2 Normalization (norm should be ~1.0)
    import math
    norm = math.sqrt(sum(x*x for x in emb1))
    assert abs(norm - 1.0) < 1e-5


# ==================== PIPELINE AND STATUS TRANSITIONS TESTS ====================

def test_pipeline_success_path(db_session: Session, mock_storage):
    _, channel = setup_workspace_and_channel(db_session, DEV_USER_ID)
    
    # Save file content in mock S3
    file_id = uuid4()
    storage_path = f"channels/{channel.id}/{file_id}/test.pdf"
    mock_storage[storage_path] = MINIMAL_PDF_BYTES
    
    # Create file record in db
    file_record = File(
        id=file_id,
        channel_id=channel.id,
        filename="test.pdf",
        storage_path=storage_path,
        uploaded_by=DEV_USER_ID,
        ingestion_status="pending",
    )
    db_session.add(file_record)
    db_session.commit()
    
    # Run pipeline
    run_ingestion_pipeline(file_id, db=db_session)
    
    # Check updated status
    db_session.refresh(file_record)
    assert file_record.ingestion_status == "completed"
    assert file_record.ingestion_error is None
    
    # Check created chunks
    chunks = db_session.scalars(select(Chunk).where(Chunk.file_id == file_id)).all()
    assert len(chunks) == 1
    assert chunks[0].page_number == 1
    assert "Hello world" in chunks[0].content
    assert len(chunks[0].embedding) == 1536
    # Denormalized channel_id matches parent file channel_id
    assert chunks[0].channel_id == channel.id


def test_pipeline_failure_path_corrupt_file(db_session: Session, mock_storage):
    _, channel = setup_workspace_and_channel(db_session, DEV_USER_ID)
    
    file_id = uuid4()
    storage_path = f"channels/{channel.id}/{file_id}/corrupt.pdf"
    mock_storage[storage_path] = b"completely corrupt bytes"
    
    file_record = File(
        id=file_id,
        channel_id=channel.id,
        filename="corrupt.pdf",
        storage_path=storage_path,
        uploaded_by=DEV_USER_ID,
        ingestion_status="pending",
    )
    db_session.add(file_record)
    db_session.commit()
    
    # Run pipeline
    run_ingestion_pipeline(file_id, db=db_session)
    
    # Check updated status
    db_session.refresh(file_record)
    assert file_record.ingestion_status == "failed"
    assert "Invalid file signature" in file_record.ingestion_error


# ==================== API ENDPOINTS TESTS ====================

def test_api_upload_flow_and_transitions(client: TestClient, db_session: Session, mock_storage):
    _, channel = setup_workspace_and_channel(db_session, DEV_USER_ID)
    
    # Upload plain text file
    response = client.post(
        f"/channels/{channel.id}/files",
        files={"file": ("hello.txt", b"Hello simple plain text file content", "text/plain")}
    )
    
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "hello.txt"
    assert body["ingestion_status"] == "pending"
    
    file_id = UUID(body["id"])
    
    # Verify in DB
    file_record = db_session.get(File, file_id)
    assert file_record is not None
    assert file_record.filename == "hello.txt"
    
    # Verify uploaded in storage
    assert file_record.storage_path in mock_storage
    
    # Process background tasks (we call pipeline directly in test since SQLite is in-memory)
    run_ingestion_pipeline(file_id, db=db_session)
    
    db_session.refresh(file_record)
    assert file_record.ingestion_status == "completed"
    
    # List files endpoint
    list_response = client.get(f"/channels/{channel.id}/files")
    assert list_response.status_code == 200
    files_list = list_response.json()
    assert len(files_list) == 1
    assert files_list[0]["id"] == str(file_id)
    assert files_list[0]["ingestion_status"] == "completed"


def test_api_download_file(client: TestClient, db_session: Session, mock_storage):
    _, channel = setup_workspace_and_channel(db_session, DEV_USER_ID)
    
    file_id = uuid4()
    storage_path = f"channels/{channel.id}/{file_id}/hello.txt"
    file_content = b"My secret message content"
    mock_storage[storage_path] = file_content
    
    file_record = File(
        id=file_id,
        channel_id=channel.id,
        filename="hello.txt",
        storage_path=storage_path,
        uploaded_by=DEV_USER_ID,
        ingestion_status="completed",
    )
    db_session.add(file_record)
    db_session.commit()
    
    # Download file
    download_response = client.get(f"/channels/{channel.id}/files/{file_id}/download")
    assert download_response.status_code == 200
    assert download_response.content == file_content
    assert "attachment; filename=\"hello.txt\"" in download_response.headers["content-disposition"]


def test_api_retry_ingestion(client: TestClient, db_session: Session, mock_storage):
    _, channel = setup_workspace_and_channel(db_session, DEV_USER_ID)
    
    file_id = uuid4()
    storage_path = f"channels/{channel.id}/{file_id}/retry.pdf"
    
    # Initially upload corrupt bytes
    mock_storage[storage_path] = b"corrupt bytes"
    
    file_record = File(
        id=file_id,
        channel_id=channel.id,
        filename="retry.pdf",
        storage_path=storage_path,
        uploaded_by=DEV_USER_ID,
        ingestion_status="failed",
        ingestion_error="Initial corrupt failure",
    )
    db_session.add(file_record)
    # Insert some dummy old chunk to verify it gets cleaned up
    dummy_chunk = Chunk(
        id=uuid4(),
        file_id=file_id,
        channel_id=channel.id,
        page_number=1,
        content="stale content",
        embedding=[0.0] * 1536
    )
    db_session.add(dummy_chunk)
    db_session.commit()
    
    # Try to retry while file is still corrupt
    retry_response = client.post(f"/channels/{channel.id}/files/{file_id}/retry-ingestion")
    assert retry_response.status_code == 200
    assert retry_response.json()["ingestion_status"] == "pending"
    assert retry_response.json()["ingestion_error"] is None
    
    # Replace storage with valid PDF file
    mock_storage[storage_path] = MINIMAL_PDF_BYTES
    
    # Trigger background tasks execution
    run_ingestion_pipeline(file_id, db=db_session)
    
    # Check that it succeeded
    db_session.refresh(file_record)
    assert file_record.ingestion_status == "completed"
    
    # Verify old stale chunk is cleaned up and only new one is present
    chunks = db_session.scalars(select(Chunk).where(Chunk.file_id == file_id)).all()
    assert len(chunks) == 1
    assert chunks[0].content != "stale content"
    assert "Hello world" in chunks[0].content


# ==================== PERMISSIONS TESTS ====================

def test_files_permissions_enforcement(client: TestClient, db_session: Session):
    # Setup owner, admin, member, read-only memberships
    _, channel = setup_workspace_and_channel(db_session, DEV_USER_ID)
    
    # Setup a second user who is read-only
    ro_user_id = uuid4()
    ro_user = User(id=ro_user_id, email="ro@example.com", password_hash="dummy")
    db_session.add(ro_user)
    db_session.flush()
    db_session.add(Membership(user_id=ro_user_id, channel_id=channel.id, role=Role.READ_ONLY.value))
    
    # Setup a third user who has no membership
    non_member_id = uuid4()
    non_member = User(id=non_member_id, email="non@example.com", password_hash="dummy")
    db_session.add(non_member)
    db_session.commit()
    
    # 1. Non-member access to channel's files (List) -> should return 404 (undisclosed existence)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=non_member_id)
    response = client.get(f"/channels/{channel.id}/files")
    assert response.status_code == 404
    
    # 2. Non-member tries to upload -> should return 404
    response = client.post(
        f"/channels/{channel.id}/files",
        files={"file": ("test.txt", b"content", "text/plain")}
    )
    assert response.status_code == 404

    # 3. Read-only member tries to upload -> should return 403 Forbidden
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=ro_user_id)
    response = client.post(
        f"/channels/{channel.id}/files",
        files={"file": ("test.txt", b"content", "text/plain")}
    )
    assert response.status_code == 403
    
    # 4. Read-only member lists files -> should succeed (200)
    response = client.get(f"/channels/{channel.id}/files")
    assert response.status_code == 200
