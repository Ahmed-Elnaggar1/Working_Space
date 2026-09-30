from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.exceptions import (
    InvalidCredentialsError,
    InvalidTokenError,
    TokenExpiredError,
    TokenReuseDetectedError,
    UserAlreadyExistsError,
    UserNotFoundError,
)
from app.auth.repositories import RefreshTokenRepository, UserRepository
from app.auth.schemas import UserLogin, UserRegister
from app.auth.security import (
    JWT_REFRESH_SECRET,
    REFRESH_TOKEN_EXPIRE,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token_sha256,
    verify_password,
)
from app.models import User


@dataclass(frozen=True)
class AuthTokens:
    access_token: str
    refresh_token: str
    refresh_token_max_age: int


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.token_repo = RefreshTokenRepository(db)

    async def register(self, payload: UserRegister) -> User:
        email = payload.email.strip().lower()

        if await self.user_repo.get_by_email(email):
            raise UserAlreadyExistsError(
                "A user with this email already exists."
            )

        try:
            user = await self.user_repo.create(
                email=email,
                password_hash=hash_password(payload.password),
            )
            await self.db.commit()
            await self.db.refresh(user)
            return user
        except IntegrityError as error:
            await self.db.rollback()
            raise UserAlreadyExistsError(
                "A user with this email already exists."
            ) from error

    async def login(self, payload: UserLogin) -> AuthTokens:
        email = payload.email.strip().lower()
        user = await self.user_repo.get_by_email(email)

        if not user or not verify_password(payload.password, user.password_hash):
            raise InvalidCredentialsError("Invalid email or password.")

        access_token = create_access_token(user.id)
        refresh_token, expires_at = create_refresh_token(user.id)

        try:
            await self.token_repo.create(
                user_id=user.id,
                token_hash=hash_token_sha256(refresh_token),
                expires_at=expires_at,
            )
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        return AuthTokens(
            access_token=access_token,
            refresh_token=refresh_token,
            refresh_token_max_age=int(REFRESH_TOKEN_EXPIRE.total_seconds()),
        )

    async def refresh(self, raw_token: str | None) -> AuthTokens:
        if not raw_token:
            raise InvalidTokenError("Refresh token is missing.")

        try:
            payload = decode_token(raw_token, JWT_REFRESH_SECRET)
            if payload.get("type") != "refresh":
                raise InvalidTokenError("Invalid token type.")
            user_id = UUID(payload["sub"])
        except (InvalidTokenError, ValueError, KeyError, TypeError) as error:
            if isinstance(error, InvalidTokenError):
                raise
            raise InvalidTokenError("Malformed refresh token.") from error

        token_hash = hash_token_sha256(raw_token)
        record = await self.token_repo.get_by_hash(token_hash)

        if not record or record.user_id != user_id:
            raise InvalidTokenError("Invalid or expired session.")

        if record.revoked_at is not None:
            await self.token_repo.revoke_all_for_user(record.user_id)
            await self.db.commit()
            raise TokenReuseDetectedError("Refresh token reuse detected.")

        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise TokenExpiredError("Refresh token has expired.")

        if not await self.token_repo.revoke_if_active(token_hash):
            await self.token_repo.revoke_all_for_user(record.user_id)
            await self.db.commit()
            raise TokenReuseDetectedError("Refresh token reuse detected.")

        try:
            new_access_token = create_access_token(user_id)
            new_refresh_token, new_expires_at = create_refresh_token(user_id)
            await self.token_repo.create(
                user_id=user_id,
                token_hash=hash_token_sha256(new_refresh_token),
                expires_at=new_expires_at,
            )
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        return AuthTokens(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            refresh_token_max_age=int(REFRESH_TOKEN_EXPIRE.total_seconds()),
        )

    async def logout(self, raw_token: str | None) -> None:
        if not raw_token:
            return

        try:
            record = await self.token_repo.get_by_hash(
                hash_token_sha256(raw_token)
            )
            if record and record.revoked_at is None:
                await self.token_repo.revoke(record)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

    async def get_user(self, user_id: UUID) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError("User not found.")
        return user
