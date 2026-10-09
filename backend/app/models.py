from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import CHAR, TypeDecorator
from pgvector.sqlalchemy import Vector


from app.core import Base


class GUID(TypeDecorator[UUID]):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PostgresUUID

            return dialect.type_descriptor(PostgresUUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value) if dialect.name != "postgresql" else value

    def process_result_value(self, value, dialect):
        return UUID(value) if value is not None and not isinstance(value, UUID) else value


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    READ_ONLY = "read_only"


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    username: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    owner: Mapped[User] = relationship()
    channels: Mapped[list["Channel"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )


class Channel(Base):
    __tablename__ = "channels"
    __table_args__ = (UniqueConstraint("workspace_id", "name", name="uq_channels_workspace_name"),)

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(ForeignKey("workspaces.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    workspace: Mapped[Workspace] = relationship(back_populates="channels")
    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )
    files: Mapped[list["File"]] = relationship(back_populates="channel", cascade="all, delete-orphan")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="channel", cascade="all, delete-orphan")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "channel_id", name="uq_memberships_user_channel"),
        CheckConstraint(
            "role IN ('owner', 'admin', 'member', 'read_only')",
            name="ck_memberships_role_valid",
        ),
        Index("ix_memberships_user_channel", "user_id", "channel_id"),
        Index("ix_memberships_channel_role", "channel_id", "role"),
    )

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    channel_id: Mapped[UUID] = mapped_column(ForeignKey("channels.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    channel: Mapped[Channel] = relationship(back_populates="memberships")


class File(Base):
    __tablename__ = "files"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    channel_id: Mapped[UUID] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    ingestion_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    ingestion_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ingestion_retry_count: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    channel: Mapped["Channel"] = relationship(back_populates="files")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="file", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index("ix_chunks_channel_id", "channel_id"),
        Index("ix_chunks_file_id", "file_id"),
    )

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    file_id: Mapped[UUID] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    channel_id: Mapped[UUID] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int | None] = mapped_column(nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector, nullable=False)

    file: Mapped["File"] = relationship(back_populates="chunks")
    channel: Mapped["Channel"] = relationship(back_populates="chunks")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_token_hash", "token_hash", unique=True),
        Index("ix_refresh_tokens_user_id", "user_id"),
    )

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index("ix_messages_channel_created_at", "channel_id", "created_at"),
        Index("ix_messages_parent_message_id", "parent_message_id"),
    )

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    channel_id: Mapped[UUID] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    parent_message_id: Mapped[UUID | None] = mapped_column(
        GUID(), ForeignKey("messages.id", ondelete="CASCADE"), nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    channel: Mapped[Channel] = relationship(back_populates="messages")
    user: Mapped[User] = relationship()
    parent: Mapped["Message | None"] = relationship(
        "Message", remote_side=[id], back_populates="replies"
    )
    replies: Mapped[list["Message"]] = relationship(
        "Message", back_populates="parent", cascade="all, delete-orphan"
    )
    mentions: Mapped[list["Mention"]] = relationship(
        "Mention", back_populates="message", cascade="all, delete-orphan"
    )


class Mention(Base):
    __tablename__ = "mentions"
    __table_args__ = (
        UniqueConstraint("message_id", "mentioned_user_id", name="uq_mentions_message_user"),
        Index("ix_mentions_mentioned_user_id", "mentioned_user_id"),
    )

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    message_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    mentioned_user_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    message: Mapped["Message"] = relationship(back_populates="mentions")
    mentioned_user: Mapped["User"] = relationship()


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "type IN ('mention', 'thread_reply')",
            name="ck_notifications_type_valid",
        ),
        Index("ix_notifications_user_unread", "user_id", "is_read"),
        Index("ix_notifications_user_created_at", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    channel_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[UUID] = mapped_column(
        GUID(), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    actor: Mapped["User"] = relationship(foreign_keys=[actor_id])
    channel: Mapped["Channel"] = relationship()
    message: Mapped["Message"] = relationship()

