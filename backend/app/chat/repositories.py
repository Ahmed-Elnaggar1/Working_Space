from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select, update
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

    async def get_by_id(self, notification_id: UUID) -> Notification | None:
        """Fetches a single notification by ID."""
        stmt = select(Notification).where(Notification.id == notification_id)
        return await self.db.scalar(stmt)

    async def get_user_notifications(
        self,
        user_id: UUID,
        limit: int = 50,
        before_created_at: datetime | None = None,
        before_id: UUID | None = None,
    ) -> tuple[list[Notification], bool]:
        """Fetches newest-first notifications for a user with cursor pagination."""
        stmt = select(Notification).where(Notification.user_id == user_id)
        if before_created_at and before_id:
            stmt = stmt.where(
                or_(
                    Notification.created_at < before_created_at,
                    (Notification.created_at == before_created_at)
                    & (Notification.id < before_id),
                )
            )
        stmt = (
            stmt.order_by(
                Notification.created_at.desc(), Notification.id.desc()
            ).limit(limit + 1)
        )
        results = list((await self.db.scalars(stmt)).all())
        has_more = len(results) > limit
        return results[:limit], has_more

    async def get_unread_count(self, user_id: UUID) -> int:
        """Counts unread notifications for a user live."""
        stmt = select(func.count(Notification.id)).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
        count = await self.db.scalar(stmt)
        return count or 0

    async def mark_as_read(
        self, user_id: UUID, notification_id: UUID
    ) -> Notification | None:
        """Marks a notification as read if it belongs to the user."""
        stmt = select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == user_id,
        )
        notif = await self.db.scalar(stmt)
        if not notif:
            return None
        notif.is_read = True
        await self.db.commit()
        await self.db.refresh(notif)
        return notif

    async def mark_all_as_read(self, user_id: UUID) -> int:
        """Marks all unread notifications for a user as read and returns count."""
        stmt = (
            update(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount or 0
