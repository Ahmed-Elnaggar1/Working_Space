import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
from jose import jwt, JWTError

from app.auth.exceptions import InvalidTokenError
from app.core.config import settings

access_secret = settings.JWT_ACCESS_SECRET or settings.JWT_SECRET
refresh_secret = settings.JWT_REFRESH_SECRET or settings.JWT_SECRET

if settings.ENV == "production" and (not access_secret or not refresh_secret):
    raise RuntimeError("JWT secrets are required in production.")

JWT_ACCESS_SECRET = access_secret or "local-access-secret-change-me"
JWT_REFRESH_SECRET = refresh_secret or "local-refresh-secret-change-me"
JWT_ALGORITHM = "HS256"

def parse_duration(duration_str: str) -> timedelta:
    units = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}
    unit = duration_str[-1]
    if unit in units and duration_str[:-1].isdigit():
        return timedelta(**{units[unit]: int(duration_str[:-1])})
    return timedelta(minutes=15)


ACCESS_TOKEN_EXPIRE = parse_duration(settings.JWT_ACCESS_EXPIRES_IN)
REFRESH_TOKEN_EXPIRE = parse_duration(settings.JWT_REFRESH_EXPIRES_IN)

def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False

def hash_token_sha256(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_access_token(user_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + ACCESS_TOKEN_EXPIRE,
    }
    return jwt.encode(payload, JWT_ACCESS_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: UUID) -> tuple[str, datetime]:
    """Returns the encoded token AND the exact expiration timestamp for DB storage."""
    now = datetime.now(timezone.utc)
    expires_at = now + REFRESH_TOKEN_EXPIRE
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": expires_at,
    }
    encoded = jwt.encode(payload, JWT_REFRESH_SECRET, algorithm=JWT_ALGORITHM)
    return encoded, expires_at

def decode_token(token: str, secret: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
    except JWTError as e:
        raise InvalidTokenError("Token decoding failed.") from e