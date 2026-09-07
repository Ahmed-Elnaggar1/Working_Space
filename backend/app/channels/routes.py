from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.db import get_db
from app.models import Channel, Membership, Role, User, Workspace
from app.channels.schemas import (
    ChannelCreate,
    ChannelResponse,
    MembershipCreate,
    MembershipResponse,
    MembershipUpdate,
)
from app.permissions import require_role

router = APIRouter(tags=["channels"])


@router.post(
    "/workspaces/{workspace_id}/channels",
    response_model=ChannelResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_channel(
    workspace_id: UUID,
    payload: ChannelCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Channel:
    workspace = await db.scalar(select(Workspace).where(Workspace.id == workspace_id))
    if workspace is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found")
    if workspace.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
    existing_channel = await db.scalar(
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
        await db.flush()
        db.add(Membership(user_id=current_user.id, channel_id=channel.id, role=Role.OWNER.value))
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        if (
            "uq_channels_workspace_name" in str(error.orig)
            or "channels.workspace_id, channels.name" in str(error.orig)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Channel name already exists in this workspace",
            ) from error
        raise
    await db.refresh(channel)
    return channel


@router.get("/channels/{channel_id}", response_model=ChannelResponse)
async def get_channel(
    channel_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Channel:
    channel = await db.scalar(
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


@router.post(
    "/channels/{channel_id}/members",
    response_model=MembershipResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("add_remove_members"))],
)
async def add_channel_member(
    channel_id: UUID,
    payload: MembershipCreate,
    db: AsyncSession = Depends(get_db),
) -> Membership:
    # Verify user exists
    user = await db.scalar(select(User).where(User.id == payload.user_id))
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Verify if user is already a member
    existing_membership = await db.scalar(
        select(Membership).where(
            Membership.user_id == payload.user_id,
            Membership.channel_id == channel_id,
        )
    )
    if existing_membership:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this channel",
        )

    membership = Membership(
        user_id=payload.user_id,
        channel_id=channel_id,
        role=payload.role.value,
    )
    db.add(membership)
    await db.commit()
    await db.refresh(membership)
    return membership


@router.patch(
    "/channels/{channel_id}/members/{user_id}",
    response_model=MembershipResponse,
    dependencies=[Depends(require_role("change_member_roles"))],
)
async def update_channel_member_role(
    channel_id: UUID,
    user_id: UUID,
    payload: MembershipUpdate,
    db: AsyncSession = Depends(get_db),
) -> Membership:
    # Find membership
    membership = await db.scalar(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.channel_id == channel_id,
        )
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    membership.role = payload.role.value
    await db.commit()
    await db.refresh(membership)
    return membership


@router.delete(
    "/channels/{channel_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_role("add_remove_members"))],
)
async def remove_channel_member(
    channel_id: UUID,
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    # Find membership
    membership = await db.scalar(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.channel_id == channel_id,
        )
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    await db.delete(membership)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

