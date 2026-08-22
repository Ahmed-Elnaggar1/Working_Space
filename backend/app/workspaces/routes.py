from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.db import get_db
from app.models import User, Workspace
from app.workspaces.schemas import WorkspaceCreate, WorkspaceResponse

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
def create_workspace(
    payload: WorkspaceCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Workspace:
    user = db.scalar(select(User).where(User.id == current_user.id))
    if user is None:
        user = User(
            id=current_user.id,
            email="dev@example.com",
            password_hash="not-used-by-dev-auth",
        )
        db.add(user)
        db.flush()

    workspace = Workspace(name=payload.name, owner_id=current_user.id)
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace
