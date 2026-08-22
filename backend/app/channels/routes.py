from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.db import get_db
from app.models import Channel, Membership, Role, Workspace
from app.channels.schemas import ChannelCreate, ChannelResponse

router = APIRouter(tags=["channels"])


@router.post(
    "/workspaces/{workspace_id}/channels",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_channel(
    workspace_id: UUID,
    payload: ChannelCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Channel:
    workspace = db.scalar(select(Workspace).where(Workspace.id == workspace_id))
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    if workspace.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    existing_channel = db.scalar(
        select(Channel).where(
            Channel.workspace_id == workspace_id,
            Channel.name == payload.name,
        )
    )
    if existing_channel is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Channel name already exists in this workspace",
        )

    channel = Channel(workspace_id=workspace_id, name=payload.name)
    db.add(channel)
    try:
        db.flush()
        db.add(Membership(user_id=current_user.id, channel_id=channel.id, role=Role.OWNER.value))
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if (
            "uq_channels_workspace_name" in str(error.orig)
            or "channels.workspace_id, channels.name" in str(error.orig)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Channel name already exists in this workspace",
            ) from error
        raise
    db.refresh(channel)
    return channel


@router.get("/channels/{channel_id}", response_model=ChannelResponse)
def get_channel(
    channel_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Channel:
    channel = db.scalar(
        select(Channel)
        .join(Membership, Membership.channel_id == Channel.id)
        .where(
            Channel.id == channel_id,
            Membership.user_id == current_user.id,
        )
    )
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    return channel
