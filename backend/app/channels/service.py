from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Channel, Membership, Role, User


async def add_member(
    db: AsyncSession,
    *,
    channel_id: UUID,
    user_id: UUID | None = None,
    email: str | None = None,
    role: Role,
) -> Membership:
    if user_id is None:
        if email is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User ID or email is required")
        user = await db.scalar(select(User).where(User.email == email.lower()))
    else:
        user = await db.scalar(select(User).where(User.id == user_id))

    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    target_user_id = user.id
    existing_membership = await db.scalar(
        select(Membership).where(
            Membership.user_id == target_user_id,
            Membership.channel_id == channel_id,
        )
    )
    if existing_membership is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this channel",
        )

    membership = Membership(user_id=target_user_id, channel_id=channel_id, role=role.value)
    db.add(membership)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        if (
            "uq_memberships_user_channel" in str(error.orig)
            or "memberships.user_id, memberships.channel_id" in str(error.orig)
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User is already a member of this channel",
            ) from error
        raise

    await db.refresh(membership)
    return membership


async def update_member_role(
    db: AsyncSession,
    *,
    channel_id: UUID,
    user_id: UUID,
    role: Role,
) -> Membership:
    await _lock_channel(db, channel_id=channel_id)
    membership = await _get_membership(db, channel_id=channel_id, user_id=user_id)
    if membership.role == Role.OWNER.value and role.value != Role.OWNER.value:
        await _ensure_another_owner_exists(db, channel_id=channel_id)

    membership.role = role.value
    await db.commit()
    await db.refresh(membership)
    return membership


async def remove_member(
    db: AsyncSession,
    *,
    channel_id: UUID,
    user_id: UUID,
) -> None:
    await _lock_channel(db, channel_id=channel_id)
    membership = await _get_membership(db, channel_id=channel_id, user_id=user_id)
    if membership.role == Role.OWNER.value:
        await _ensure_another_owner_exists(db, channel_id=channel_id)

    await db.delete(membership)
    await db.commit()


async def _get_membership(
    db: AsyncSession,
    *,
    channel_id: UUID,
    user_id: UUID,
) -> Membership:
    membership = await db.scalar(
        select(Membership).where(
            Membership.user_id == user_id,
            Membership.channel_id == channel_id,
        )
    )
    if membership is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")
    return membership


async def _lock_channel(db: AsyncSession, *, channel_id: UUID) -> Channel:
    channel = await db.scalar(
        select(Channel).where(Channel.id == channel_id).with_for_update()
    )
    if channel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")
    return channel


async def _ensure_another_owner_exists(db: AsyncSession, *, channel_id: UUID) -> None:
    owner_count = await db.scalar(
        select(func.count(Membership.id)).where(
            Membership.channel_id == channel_id,
            Membership.role == Role.OWNER.value,
        )
    )
    if owner_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A channel must retain at least one owner",
        )
