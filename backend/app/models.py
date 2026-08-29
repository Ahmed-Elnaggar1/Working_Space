from datetime import datetime, timezone
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import CHAR, TypeDecorator
from pgvector.sqlalchemy import Vector


from app.db import Base


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
    files: Mapped[list["File"]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )



class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "channel_id", name="uq_memberships_user_channel"),
        Index("ix_memberships_user_channel", "user_id", "channel_id"),
        Index("ix_memberships_channel_role", "channel_id", "role"),
    )

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    channel_id: Mapped[UUID] = mapped_column(ForeignKey("channels.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    channel: Mapped[Channel] = relationship(back_populates="memberships")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class File(Base):
    __tablename__ = "files"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    channel_id: Mapped[UUID] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    uploaded_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    ingestion_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    ingestion_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    channel: Mapped["Channel"] = relationship(back_populates="files")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="file", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[UUID] = mapped_column(GUID(), primary_key=True, default=uuid4)
    file_id: Mapped[UUID] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), nullable=False)
    channel_id: Mapped[UUID] = mapped_column(ForeignKey("channels.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int | None] = mapped_column(nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)

    file: Mapped["File"] = relationship(back_populates="chunks")

