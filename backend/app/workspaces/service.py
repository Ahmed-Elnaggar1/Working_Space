from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select, exists

from app.models import Channel, Membership, Role, Workspace
from app.workspaces.schemas import WorkspaceCreate


async def create_workspace_with_defaults(
        db : AsyncSession,
        *,
        payload: WorkspaceCreate,
        owner_id: UUID,
)-> Workspace:
    """Creates a workspace, its default channel, and assigns the owner membership atomically."""
    workspace = Workspace(
        name = payload.name,
        owner_id = owner_id,
        channels=[
            Channel(
                name = "general",
                memberships = [
                    Membership(user_id = owner_id, role = Role.OWNER),
                ],
            )
        ],
    )
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    return workspace

async def get_user_workspaces(
        db : AsyncSession,
        *,
        user_id : UUID
)-> list[Workspace]:
    """Fetches all workspaces where the user is either the owner
    or a member of at least one channel.
    """
    has_channel_membership = exists(
        select(Membership.id)
        .join(Channel, Channel.id == Membership.channel_id)
        .where(
            Channel.workspace_id == Workspace.id,
            Membership.user_id == user_id,
        )
    )

    stmt = (
        select(Workspace)
        .where(or_(Workspace.owner_id == user_id, has_channel_membership))
        .order_by(Workspace.created_at.desc())
    )
    result = await db.scalars(stmt)
    return list(result.all())


async def get_workspace_for_user(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    user_id: UUID,
) -> Workspace | None:
    """Fetches a specific workspace only if the user is the owner
    or a member of at least one channel in that workspace.
    Shared access check with get_user_workspaces (S6-01 / S6-02).
    """
    has_channel_membership = exists(
        select(Membership.id)
        .join(Channel, Channel.id == Membership.channel_id)
        .where(
            Channel.workspace_id == Workspace.id,
            Membership.user_id == user_id,
        )
    )

    stmt = select(Workspace).where(
        Workspace.id == workspace_id,
        or_(Workspace.owner_id == user_id, has_channel_membership),
    )
    return await db.scalar(stmt)


async def get_workspace_channels_for_user(
    db: AsyncSession,
    *,
    workspace_id: UUID,
    user_id: UUID,
) -> list[Channel]:
    """Lists only the channels within the workspace the caller is a member of (S6-03)."""
    stmt = (
        select(Channel)
        .join(Membership, Membership.channel_id == Channel.id)
        .where(
            Channel.workspace_id == workspace_id,
            Membership.user_id == user_id,
        )
        .order_by(Channel.created_at.asc())
    )
    result = await db.scalars(stmt)
    return list(result.all())
