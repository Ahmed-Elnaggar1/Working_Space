from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.schemas import MessageCreate
from app.models import Message


async def persist_message(
    db: AsyncSession,
    channel_id: UUID,
    user_id: UUID,
    payload: MessageCreate,
) -> Message:
    message = Message(
        channel_id=channel_id,
        user_id=user_id,
        content=payload.content,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message
