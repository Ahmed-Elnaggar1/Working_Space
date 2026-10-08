from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Message, Notification


class MessageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, message_id: UUID) -> Message | None:
        """Fetches a single message by ID."""
        stmt = select(Message).where(Message.id == message_id)
        return await self.db.scalar(stmt)

    async def create(
        self,
        channel_id: UUID,
        user_id: UUID,
        content: str,
        parent_message_id: UUID | None = None,
    ) -> Message:
        """Adds a new message to the session."""
        message = Message(
            channel_id=channel_id,
            user_id=user_id,
            content=content,
            parent_message_id=parent_message_id,
        )
        self.db.add(message)
        await self.db.flush()
        return message

    async def get_thread_replies(self, parent_message_id: UUID) -> list[Message]:
        """Returns all replies for a thread ordered chronologically (S11-06)."""
        stmt = (
            select(Message)
            .where(Message.parent_message_id == parent_message_id)
            .order_by(Message.created_at.asc())
        )
        result = await self.db.scalars(stmt)
        return list(result.all())

    async def get_thread_participant_ids(
        self, parent_message: Message
    ) -> set[UUID]:
        """
        Returns all unique user IDs involved in a thread (S11-07):
        - The parent message author
        - All previous repliers in the thread
        """
        stmt = select(Message.user_id).where(
            Message.parent_message_id == parent_message.id
        )
        replier_ids = set((await self.db.scalars(stmt)).all())
        replier_ids.add(parent_message.user_id)
        return replier_ids

class NotificationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def add_many(self, notifications: list[Notification]) -> None:
        """Adds a list of notifications to the current session."""
        self.db.add_all(notifications)
