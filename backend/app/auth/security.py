import os
import hashlib
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt, JWTError

# Load environment configuration
JWT_ACCESS_SECRET = os.getenv("JWT_ACCESS_SECRET", "dev-access-secret-key-change-in-production-1234567890")
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", "dev-refresh-secret-key-change-in-production-1234567890")
JWT_ALGORITHM = "HS256"

# Default expirations
ACCESS_EXPIRE_STR = os.getenv("JWT_ACCESS_EXPIRES_IN", "15m")
REFRESH_EXPIRE_STR = os.getenv("JWT_REFRESH_EXPIRES_IN", "7d")


def parse_duration(duration_str: str) -> timedelta:
    if duration_str.endswith("m"):
        return timedelta(minutes=int(duration_str[:-1]))
    elif duration_str.endswith("d"):
        return timedelta(days=int(duration_str[:-1]))
    elif duration_str.endswith("h"):
        return timedelta(hours=int(duration_str[:-1]))
    elif duration_str.endswith("s"):
        return timedelta(seconds=int(duration_str[:-1]))
    return timedelta(minutes=15)


ACCESS_TOKEN_EXPIRE_TIMEDELTA = parse_duration(ACCESS_EXPIRE_STR)
REFRESH_TOKEN_EXPIRE_TIMEDELTA = parse_duration(REFRESH_EXPIRE_STR)


def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pwd_bytes = plain_password.encode("utf-8")
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + ACCESS_TOKEN_EXPIRE_TIMEDELTA
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, JWT_ACCESS_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    import uuid
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + REFRESH_TOKEN_EXPIRE_TIMEDELTA
    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid.uuid4())
    })
    return jwt.encode(to_encode, JWT_REFRESH_SECRET, algorithm=JWT_ALGORITHM)



def decode_token(token: str, secret: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}")


def hash_token_sha256(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
