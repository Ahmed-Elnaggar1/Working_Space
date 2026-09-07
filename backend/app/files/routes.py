import io
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
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.db import get_db
from app.files.schemas import FileResponse
from app.files.storage import storage
from app.ingestion.pipeline import run_ingestion_pipeline
from app.models import File, Membership
from app.permissions import require_role

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
    file_id = uuid4()
    content = await file.read()
    storage_path = f"channels/{channel_id}/{file_id}/{file.filename or 'upload'}"

    try:
        storage.upload_file(storage_path, content, file.content_type or "application/octet-stream")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store uploaded file: {str(exc)}",
        ) from exc

    file_record = File(
        id=file_id,
        channel_id=channel_id,
        filename=file.filename or "upload",
        storage_path=storage_path,
        uploaded_by=current_user.id,
        ingestion_status="pending",
        ingestion_error=None,
    )
    db.add(file_record)
    db.commit()
    db.refresh(file_record)

    background_tasks.add_task(run_ingestion_pipeline, file_record.id)

    return {
        "id": file_record.id,
        "channel_id": file_record.channel_id,
        "filename": file_record.filename,
        "file_name": file_record.filename,
        "storage_path": file_record.storage_path,
        "uploaded_by": file_record.uploaded_by,
        "ingestion_status": file_record.ingestion_status,
        "ingestion_error": file_record.ingestion_error,
        "created_at": file_record.created_at,
    }


@router.get(
    "/channels/{channel_id}/files",
    response_model=list[FileResponse],
)
def list_files(
    channel_id: UUID,
    db: Session = Depends(get_db),
    _membership: Membership = Depends(require_role("view_files")),
):
    files = db.scalars(select(File).where(File.channel_id == channel_id)).all()
    return [
        {
            "id": record.id,
            "channel_id": record.channel_id,
            "filename": record.filename,
            "file_name": record.filename,
            "storage_path": record.storage_path,
            "uploaded_by": record.uploaded_by,
            "ingestion_status": record.ingestion_status,
            "ingestion_error": record.ingestion_error,
            "created_at": record.created_at,
        }
        for record in files
    ]


@router.get(
    "/channels/{channel_id}/files/{file_id}/download",
)
def download_file(
    channel_id: UUID,
    file_id: UUID,
    db: Session = Depends(get_db),
    _membership: Membership = Depends(require_role("view_files")),
):
    file_record = db.scalar(select(File).where(File.id == file_id, File.channel_id == channel_id))
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
def retry_ingestion(
    channel_id: UUID,
    file_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _membership: Membership = Depends(require_role("upload_files")),
):
    file_record = db.scalar(select(File).where(File.id == file_id, File.channel_id == channel_id))
    if not file_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if file_record.ingestion_status != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed file ingestions can be retried",
        )

    file_record.ingestion_status = "pending"
    file_record.ingestion_error = None
    db.commit()
    db.refresh(file_record)

    background_tasks.add_task(run_ingestion_pipeline, file_record.id)

    return {
        "id": file_record.id,
        "channel_id": file_record.channel_id,
        "filename": file_record.filename,
        "file_name": file_record.filename,
        "storage_path": file_record.storage_path,
        "uploaded_by": file_record.uploaded_by,
        "ingestion_status": file_record.ingestion_status,
        "ingestion_error": file_record.ingestion_error,
        "created_at": file_record.created_at,
    }


@router.delete(
    "/channels/{channel_id}/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_file(
    channel_id: UUID,
    file_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
    _membership: Membership = Depends(require_role("delete_own_file")),
):
    file_record = db.scalar(select(File).where(File.id == file_id, File.channel_id == channel_id))
    if file_record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.channel_id == channel_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    if membership.role == "read_only":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    if membership.role == "member":
        if file_record.uploaded_by != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    elif membership.role not in {"owner", "admin"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    try:
        storage.delete_file(file_record.storage_path)
    except Exception:
        pass

    db.delete(file_record)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
