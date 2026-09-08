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
