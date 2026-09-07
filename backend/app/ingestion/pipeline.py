from uuid import UUID
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import File, Chunk
from app.files.storage import storage
from app.ingestion.parser import parse_file, ParsingError
from app.ingestion.chunker import chunk_parsed_content
from app.ingestion.embeddings import generate_embedding


def run_ingestion_pipeline(file_id: UUID, db: Session | None = None) -> None:
    """Runs the ingestion pipeline for a given file ID.
    
    Coordinates downloading from storage, parsing, chunking, embedding generation,
    and database storage. This runs inside FastAPI BackgroundTasks with its own
    isolated session to ensure thread safety, but supports injecting a session for tests.
    """
    if db is not None:
        _run_ingestion(file_id, db)
    else:
        # Import locally to avoid circular dependency
        from app.main import app
        test_session_factory = getattr(app.state, "test_session_factory", None)
        if test_session_factory is not None:
            # We are in a unit test environment, use the test session directly
            session = test_session_factory()
            _run_ingestion(file_id, session)
        else:
            # Normal background task thread
            with SessionLocal() as session:
                _run_ingestion(file_id, session)


def _run_ingestion(file_id: UUID, db: Session) -> None:
    file_record = db.get(File, file_id)
    if not file_record:
        return

    try:
        # 1. Update status to processing
        file_record.ingestion_status = "processing"
        file_record.ingestion_error = None
        db.commit()

        # 2. Clean up any existing chunks (for retry idempotency)
        db.query(Chunk).filter(Chunk.file_id == file_id).delete()
        db.commit()

        # 3. Download the file bytes from storage
        file_bytes = storage.download_file(file_record.storage_path)

        # 4. Parse the file contents
        pages_content = parse_file(file_record.filename, file_bytes)
        if not pages_content or not any(text.strip() for _, text in pages_content):
            raise ParsingError("No readable text content found in the file.")

        # 5. Split text into chunks
        chunks_data = chunk_parsed_content(pages_content)
        if not chunks_data:
            raise ParsingError("Could not extract any chunks from the document content.")

        # 6. Generate embeddings and save chunks
        for chunk_dict in chunks_data:
            text_content = chunk_dict["content"]
            page_num = chunk_dict["page_number"]

            embedding = generate_embedding(text_content)

            chunk_record = Chunk(
                file_id=file_id,
                channel_id=file_record.channel_id,  # Denormalized from file for fast permissions filtering
                page_number=page_num,
                section=None,
                content=text_content,
                embedding=embedding,
            )
            db.add(chunk_record)

        # 7. Update status to completed
        file_record.ingestion_status = "completed"
        db.commit()

    except Exception as e:
        db.rollback()
        # If any step fails, capture the exception and mark the file as failed
        error_msg = str(e) if isinstance(e, ParsingError) else f"Ingestion failed: {str(e)}"
        file_record.ingestion_status = "failed"
        file_record.ingestion_error = error_msg
        db.commit()
