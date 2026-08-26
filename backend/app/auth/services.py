from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.repositories import RefreshTokenRepository, UserRepository
from app.auth.schemas import UserLogin, UserRegister
from app.auth.security import (
    JWT_REFRESH_SECRET,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token_sha256,
    verify_password,
)
from app.models import User


class AuthService:
    @staticmethod
    def register(db: Session, payload: UserRegister) -> User:
        email = payload.email.strip().lower()
        
        # Check if user already exists
        existing_user = UserRepository.get_by_email(db, email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists",
            )
        
        # Hash password and create user
        password_hash = hash_password(payload.password)
        user = UserRepository.create(db, email, password_hash)
        
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def login(db: Session, payload: UserLogin) -> tuple[User, str, str]:
        email = payload.email.strip().lower()
        
        # Find user
        user = UserRepository.get_by_email(db, email)
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        
        # Generate tokens
        access_token = create_access_token({"sub": str(user.id)})
        refresh_token = create_refresh_token({"sub": str(user.id)})
        
        # Decode refresh token to get exact expiration timestamp
        try:
            decoded = decode_token(refresh_token, JWT_REFRESH_SECRET)
            expires_at = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        except Exception:
            # Fallback to standard 7 days if decoding fails
            from datetime import timedelta
            expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        
        # Persist refresh token hash
        token_hash = hash_token_sha256(refresh_token)
        RefreshTokenRepository.create(db, user.id, token_hash, expires_at)
        
        db.commit()
        return user, access_token, refresh_token

    @staticmethod
    def refresh(db: Session, refresh_token: str) -> tuple[str, str]:
        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token missing",
            )

        # Verify/decode signature
        try:
            payload = decode_token(refresh_token, JWT_REFRESH_SECRET)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid refresh token: {e}",
            )

        # Validate token type
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        try:
            user_id = UUID(payload["sub"])
        except (ValueError, KeyError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token subject",
            )

        # Find persisted refresh token
        token_hash = hash_token_sha256(refresh_token)
        record = RefreshTokenRepository.get_by_hash(db, token_hash)

        if not record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not found",
            )

        # Check for token reuse (token has already been revoked)
        if record.revoked_at is not None:
            # Breach detected: revoke all active tokens for this user
            RefreshTokenRepository.revoke_all_for_user(db, record.user_id)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session expired due to token reuse",
            )

        # Check expiration
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
            
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token expired",
            )

        if record.user_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid user for this token",
            )

        # Issue rotated tokens
        new_access_token = create_access_token({"sub": str(user_id)})
        new_refresh_token = create_refresh_token({"sub": str(user_id)})

        # Revoke old token
        RefreshTokenRepository.revoke(db, record)

        # Persist new token hash
        try:
            new_decoded = decode_token(new_refresh_token, JWT_REFRESH_SECRET)
            new_expires_at = datetime.fromtimestamp(new_decoded["exp"], tz=timezone.utc)
        except Exception:
            from datetime import timedelta
            new_expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        new_token_hash = hash_token_sha256(new_refresh_token)
        RefreshTokenRepository.create(db, user_id, new_token_hash, new_expires_at)

        db.commit()
        return new_access_token, new_refresh_token

    @staticmethod
    def logout(db: Session, refresh_token: str | None) -> None:
        if not refresh_token:
            return

        try:
            # We don't strictly require full validation on logout to allow users to log out even if token expired,
            # but we extract the hash to invalidate it in database if it exists.
            token_hash = hash_token_sha256(refresh_token)
            record = RefreshTokenRepository.get_by_hash(db, token_hash)
            if record and record.revoked_at is None:
                RefreshTokenRepository.revoke(db, record)
                db.commit()
        except Exception:
            # Make logout completely safe/no-op on error
            pass
