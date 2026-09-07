from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.core.db import get_db
from app.models import User, Workspace
from app.workspaces.schemas import WorkspaceCreate, WorkspaceResponse

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    payload: WorkspaceCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    user = await db.scalar(select(User).where(User.id == current_user.id))
    if user is None:
        user = User(
            id=current_user.id,
            email="dev@example.com",
            password_hash="not-used-by-dev-auth",
        )
        db.add(user)
        await db.flush()

    workspace = Workspace(name=payload.name, owner_id=current_user.id)
    db.add(workspace)
    await db.commit()
    await db.refresh(workspace)
    return workspace
