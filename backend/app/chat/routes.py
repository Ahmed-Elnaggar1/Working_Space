from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.chat.schemas import MessageCreate, MessageResponse
from app.db import get_db
from app.models import Message
from app.permissions import require_role

router = APIRouter(tags=["chat"])


@router.post(
    "/channels/{channel_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("send_messages"))],
)
def create_message(
    channel_id: UUID,
    payload: MessageCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Message:
    message = Message(
        channel_id=channel_id,
        user_id=current_user.id,
        content=payload.content,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.get(
    "/channels/{channel_id}/messages",
    response_model=list[MessageResponse],
    dependencies=[Depends(require_role("view_messages"))],
)
def get_messages(
    channel_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[Message]:
    messages = (
        db.scalars(
            select(Message)
            .where(Message.channel_id == channel_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .offset(offset)
            .limit(limit)
        )
        .all()
    )
    return list(messages)
