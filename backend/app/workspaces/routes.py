from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user
from app.channels.schemas import ChannelResponse
from app.core import get_db
from app.workspaces import service
from app.workspaces.schemas import WorkspaceCreate, WorkspaceResponse

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[CurrentUser, Depends(get_current_user)]


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
)
@router.post(
    "/",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
async def create_workspace(
    payload: WorkspaceCreate,
    current_user: UserDep,
    db: SessionDep,
) -> WorkspaceResponse:
    workspace = await service.create_workspace_with_defaults(
        db,
        payload=payload,
        owner_id=current_user.id,
    )
    return workspace


@router.get(
    "",
    response_model=list[WorkspaceResponse],
    summary="List all accessible workspaces (S6-01)",
)
@router.get(
    "/",
    response_model=list[WorkspaceResponse],
    include_in_schema=False,
)
async def list_workspaces(
    current_user: UserDep,
    db: SessionDep,
) -> list[WorkspaceResponse]:
    return await service.get_user_workspaces(db, user_id=current_user.id)


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Get a specific workspace by ID (S6-02)",
)
async def get_workspace(
    workspace_id: UUID,
    current_user: UserDep,
    db: SessionDep,
) -> WorkspaceResponse:
    workspace = await service.get_workspace_for_user(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    return workspace


@router.get(
    "/{workspace_id}/channels",
    response_model=list[ChannelResponse],
    summary="List caller's channels within a workspace (S6-03)",
)
async def list_workspace_channels(
    workspace_id: UUID,
    current_user: UserDep,
    db: SessionDep,
) -> list[ChannelResponse]:
    # First verify access to the workspace via shared check (S6-02 / S2-07 404 anti-reconnaissance)
    workspace = await service.get_workspace_for_user(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found",
        )
    return await service.get_workspace_channels_for_user(
        db,
        workspace_id=workspace_id,
        user_id=current_user.id,
    )