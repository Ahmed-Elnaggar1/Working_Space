from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import RefreshToken, User


class UserRepository:
    @staticmethod
    def get_by_email(db: Session, email: str) -> User | None:
        return db.scalar(select(User).where(User.email == email))

    @staticmethod
    def get_by_id(db: Session, user_id: UUID) -> User | None:
        return db.scalar(select(User).where(User.id == user_id))

    @staticmethod
    def create(db: Session, email: str, password_hash: str) -> User:
        user = User(email=email, password_hash=password_hash)
        db.add(user)
        db.flush()
        return user


class RefreshTokenRepository:
    @staticmethod
    def create(db: Session, user_id: UUID, token_hash: str, expires_at: datetime) -> RefreshToken:
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
        db.flush()
        return token_record

    @staticmethod
    def get_by_hash(db: Session, token_hash: str) -> RefreshToken | None:
        return db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))

    @staticmethod
    def revoke(db: Session, token_record: RefreshToken) -> None:
        token_record.revoked_at = datetime.now(timezone.utc)
        db.flush()

    @staticmethod
    def revoke_all_for_user(db: Session, user_id: UUID) -> None:
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .where(RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        db.flush()
