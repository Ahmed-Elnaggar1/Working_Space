from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File as FastFile, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.db import get_db
from app.models import Channel, File, Membership
from app.permissions import require_role

router = APIRouter(tags=["files"])


def _require_channel_membership(db: Session, current_user: CurrentUser, channel_id: UUID) -> Channel:
    channel = db.scalar(
        select(Channel)
        .join(Membership, Membership.channel_id == Channel.id)
        .where(Channel.id == channel_id, Membership.user_id == current_user.id)
    )
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    return channel


def _require_file_access(db: Session, current_user: CurrentUser, channel_id: UUID, file_id: UUID) -> File:
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
    return file_record


@router.post(
    "/channels/{channel_id}/files",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("upload_files"))],
)
def upload_file(
    channel_id: UUID,
    file: UploadFile = FastFile(...),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_channel_membership(db, current_user, channel_id)

    allowed_types = {"text/plain", "application/pdf"}
    if file.content_type not in allowed_types and not (
        file.filename and file.filename.lower().endswith((".txt", ".pdf"))
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unsupported file type")

    storage_root = Path("/tmp") / "vault-storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    staged_path = storage_root / f"{uuid4()}-{file.filename or 'upload'}"
    staged_path.write_bytes(file.file.read())

    file_record = File(
        channel_id=channel_id,
        filename=file.filename or "upload",
        storage_path=str(staged_path),
        uploaded_by=current_user.id,
        ingestion_status="pending",
    )
    db.add(file_record)
    db.commit()
    db.refresh(file_record)

    return {
        "id": file_record.id,
        "channel_id": file_record.channel_id,
        "filename": file_record.filename,
        "file_name": file_record.filename,
        "storage_path": file_record.storage_path,
        "uploaded_by": file_record.uploaded_by,
        "ingestion_status": file_record.ingestion_status,
        "created_at": file_record.created_at,
    }


@router.get(
    "/channels/{channel_id}/files",
    dependencies=[Depends(require_role("view_files"))],
)
def list_files(
    channel_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_channel_membership(db, current_user, channel_id)
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
            "created_at": record.created_at,
        }
        for record in files
    ]


@router.get(
    "/channels/{channel_id}/files/{file_id}/download",
    dependencies=[Depends(require_role("view_files"))],
)
def download_file(
    channel_id: UUID,
    file_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    file_record = _require_file_access(db, current_user, channel_id, file_id)
    path = Path(file_record.storage_path)
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return FileResponse(path=path, filename=file_record.filename)


@router.delete(
    "/channels/{channel_id}/files/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_file(
    channel_id: UUID,
    file_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    file_record = _require_file_access(db, current_user, channel_id, file_id)

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

    storage_path = Path(file_record.storage_path)
    if storage_path.exists():
        storage_path.unlink()
    db.delete(file_record)
    db.commit()
    return None
