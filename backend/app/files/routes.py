import io
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, UploadFile, BackgroundTasks, status, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.db import get_db
from app.models import File, Membership
from app.permissions import require_role
from app.files.storage import storage
from app.ingestion.pipeline import run_ingestion_pipeline
from app.files.schemas import FileResponse

router = APIRouter(tags=["files"])


@router.post(
    "/channels/{channel_id}/files",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_file(
    channel_id: UUID,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    _membership: Membership = Depends(require_role("upload_files")),
):
    """Uploads a file to a channel.
    
    Verifies that the caller has upload permission. Saves file metadata,
    uploads the file bytes to S3 object storage, and queues the text ingestion
    pipeline as a background task.
    """
    file_id = uuid4()
    content = await file.read()
    
    # Generate S3 key path
    storage_path = f"channels/{channel_id}/{file_id}/{file.filename}"
    
    try:
        # Upload bytes to S3/MinIO
        storage.upload_file(storage_path, content, file.content_type)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store uploaded file: {str(e)}"
        )

    # Save metadata row
    file_record = File(
        id=file_id,
        channel_id=channel_id,
        filename=file.filename,
        storage_path=storage_path,
        uploaded_by=current_user.id,
        ingestion_status="pending",
        ingestion_error=None,
    )
    db.add(file_record)
    db.commit()
    db.refresh(file_record)

    # Queue background task to parse, chunk, embed, and store in vector db
    background_tasks.add_task(run_ingestion_pipeline, file_record.id)

    return file_record


@router.get(
    "/channels/{channel_id}/files",
    response_model=list[FileResponse],
)
def list_files(
    channel_id: UUID,
    db: Session = Depends(get_db),
    _membership: Membership = Depends(require_role("view_files")),
):
    """Lists files uploaded to a channel.
    
    Requires channel membership and view files permission.
    """
    files = db.scalars(select(File).where(File.channel_id == channel_id)).all()
    return files


@router.get(
    "/channels/{channel_id}/files/{file_id}/download",
)
def download_file(
    channel_id: UUID,
    file_id: UUID,
    db: Session = Depends(get_db),
    _membership: Membership = Depends(require_role("view_files")),
):
    """Downloads a file's raw content.
    
    Verifies both file channel context and membership before downloading.
    """
    file_record = db.scalar(
        select(File).where(File.id == file_id, File.channel_id == channel_id)
    )
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    try:
        file_bytes = storage.download_file(file_record.storage_path)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File content not found in storage: {str(e)}"
        )

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{file_record.filename}"'},
    )


@router.post(
    "/channels/{channel_id}/files/{file_id}/retry-ingestion",
    response_model=FileResponse,
)
def retry_ingestion(
    channel_id: UUID,
    file_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _membership: Membership = Depends(require_role("upload_files")),
):
    """Retries parsing and embedding ingestion for a failed upload.
    
    Clears out any previous ingestion attempts and restarts the pipeline.
    """
    file_record = db.scalar(
        select(File).where(File.id == file_id, File.channel_id == channel_id)
    )
    if not file_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File not found"
        )

    if file_record.ingestion_status != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed file ingestions can be retried"
        )

    # Reset metadata back to pending
    file_record.ingestion_status = "pending"
    file_record.ingestion_error = None
    db.commit()
    db.refresh(file_record)

    # Queue background task to retry the ingestion pipeline
    background_tasks.add_task(run_ingestion_pipeline, file_record.id)

    return file_record
