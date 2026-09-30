import io
import logging
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.config import get_settings
from app.core.db import get_db
from app.files.schemas import FileResponse
from app.files.storage import storage
from app.ingestion.pipeline import run_ingestion_pipeline
from app.models import File, Membership
from app.permissions import require_role

logger = logging.getLogger(__name__)

router = APIRouter(tags=["files"])

ALLOWED_EXTENSIONS = {".pdf", ".txt"}
ALLOWED_MIME_TYPES = {
    ".pdf": {"application/pdf"},
    ".txt": {"text/plain"},
}


def _file_response(file_record: File) -> dict:
    return {
        "id": file_record.id,
        "channel_id": file_record.channel_id,
        "filename": file_record.filename,
        "file_name": file_record.filename,
        "storage_path": file_record.storage_path,
        "uploaded_by": file_record.uploaded_by,
        "ingestion_status": file_record.ingestion_status,
        "ingestion_error": file_record.ingestion_error,
        "ingestion_retry_count": file_record.ingestion_retry_count,
        "created_at": file_record.created_at,
    }


# Upload files
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
    db: AsyncSession = Depends(get_db),
    _membership: Membership = Depends(require_role("upload_files")),
):
    # Sanitize filename and validate supported file extensions
    raw_filename = file.filename or "upload"
    safe_filename = Path(raw_filename).name or "upload"
    extension = Path(safe_filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Only PDF (.pdf) and plain text (.txt) files are supported.",
        )

    content_type = (file.content_type or "").lower().split(";", 1)[0].strip()
    if content_type not in ALLOWED_MIME_TYPES[extension]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"MIME type {content_type or 'unknown'} is not valid for {extension} files.",
        )

    file_id = uuid4()
    settings = get_settings()
    content = await file.read(settings.MAX_FILE_SIZE_BYTES + 1)
    if len(content) > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the maximum allowed size of {settings.MAX_FILE_SIZE_BYTES} bytes.",
        )
    storage_path = f"channels/{channel_id}/{file_id}/{safe_filename}"

    try:
        storage.upload_file(storage_path, content, file.content_type or "application/octet-stream")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store uploaded file: {str(exc)}",
        ) from exc

    # a file is created with pending ingestion status, and then run_ingestion_pipeline is called in background tasks
    # this is done to make the API response faster, as the file is already uploaded and ready to be used
    file_record = File(
        id=file_id,
        channel_id=channel_id,
        filename=safe_filename,
        storage_path=storage_path,
        uploaded_by=current_user.id,
        ingestion_status="pending",
        ingestion_error=None,
    )
    db.add(file_record)
    await db.commit()
    await db.refresh(file_record)

    background_tasks.add_task(run_ingestion_pipeline, file_record.id)

    return _file_response(file_record)


@router.get(
    "/channels/{channel_id}/files",
    response_model=list[FileResponse],
)
async def list_files(
    channel_id: UUID,
    db: AsyncSession = Depends(get_db),
    _membership: Membership = Depends(require_role("view_files")),
):
    files = (await db.scalars(select(File).where(File.channel_id == channel_id))).all()
    return [
        _file_response(record)
        for record in files
    ]


@router.get(
    "/channels/{channel_id}/files/{file_id}/download",
)
async def download_file(
    channel_id: UUID,
    file_id: UUID,
    db: AsyncSession = Depends(get_db),
    _membership: Membership = Depends(require_role("view_files")),
):
    file_record = await db.scalar(select(File).where(File.id == file_id, File.channel_id == channel_id))
    if not file_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    try:
        file_bytes = storage.download_file(file_record.storage_path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File content not found in storage: {str(exc)}",
        ) from exc

    return StreamingResponse(
        io.BytesIO(file_bytes),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{file_record.filename}"'},
    )


@router.post(
    "/channels/{channel_id}/files/{file_id}/retry-ingestion",
    response_model=FileResponse,
)
async def retry_ingestion(
    channel_id: UUID,
    file_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _membership: Membership = Depends(require_role("upload_files")),
):
    file_record = await db.scalar(select(File).where(File.id == file_id, File.channel_id == channel_id))
    if not file_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if file_record.ingestion_status == "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Completed file ingestions cannot be retried",
        )

    settings = get_settings()
    if file_record.ingestion_retry_count >= settings.MAX_INGESTION_RETRIES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="The maximum number of ingestion retries has been reached.",
        )

    file_record.ingestion_status = "pending"
    file_record.ingestion_error = None
    file_record.ingestion_retry_count += 1
    await db.commit()
    await db.refresh(file_record)

    background_tasks.add_task(run_ingestion_pipeline, file_record.id)

    return _file_response(file_record)


@router.delete(
    "/channels/{channel_id}/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_file(
    channel_id: UUID,
    file_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _membership: Membership = Depends(require_role("delete_own_file")),
):
    file_record = await db.scalar(select(File).where(File.id == file_id, File.channel_id == channel_id))
    if file_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if _membership.role == "read_only":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    if _membership.role == "member":
        if file_record.uploaded_by != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    elif _membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    try:
        storage.delete_file(file_record.storage_path)
    except Exception as exc:
        logger.warning("Failed to delete storage file %s: %s", file_record.storage_path, exc)

    await db.delete(file_record)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
