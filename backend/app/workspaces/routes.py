from typing import Annotated
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.core import get_db
from app.workspaces import service
from app.workspaces.schemas import WorkspaceCreate, WorkspaceResponse

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[CurrentUser, Depends(get_current_user)]

@router.post(
    "/",
    response_model=WorkspaceResponse,
    status_code= status.HTTP_201_CREATED,
    summary="Create a new workspace",
)
async def create_workspace(
    payload:WorkspaceCreate,
    current_user:UserDep,
    db:SessionDep,
) -> WorkspaceResponse:
    workspace = await service.create_workspace_with_defaults(
        db,
        payload = payload,
        owner_id = current_user.id,
    )
    return workspace

@router.get(
    "/",
    response_model = list[WorkspaceResponse],
    summary = "List all accessible workspaces",
)
async def list_workspaces(
    current_user: UserDep,
    db: SessionDep,
) -> list[WorkspaceResponse]:
    return await service.get_user_workspaces(db, user_id=current_user.id)