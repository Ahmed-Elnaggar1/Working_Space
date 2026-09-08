from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession

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