from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RefreshToken, User


class UserRepository:
    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> User | None:
        return await db.scalar(select(User).where(User.email == email))

    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: UUID) -> User | None:
        return await db.scalar(select(User).where(User.id == user_id))

    @staticmethod
    async def create(db: AsyncSession, email: str, password_hash: str) -> User:
        user = User(email=email, password_hash=password_hash)
        db.add(user)
        await db.flush()
        return user


class RefreshTokenRepository:
    @staticmethod
    async def create(db: AsyncSession, user_id: UUID, token_hash: str, expires_at: datetime) -> RefreshToken:
        # Normalize expires_at to timezone-aware UTC if it is naive
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        token_record = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked_at=None,
        )
        db.add(token_record)
        await db.flush()
        return token_record

    @staticmethod
    async def get_by_hash(db: AsyncSession, token_hash: str) -> RefreshToken | None:
        return await db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    @staticmethod
    async def revoke(db: AsyncSession, token_record: RefreshToken) -> None:
        token_record.revoked_at = datetime.now(timezone.utc)
        await db.flush()

    @staticmethod
    async def revoke_all_for_user(db: AsyncSession, user_id: UUID) -> None:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await db.flush()
