from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.security import verify_password

from app.core import Base, get_db
from app.main import app
from app.models import RefreshToken, User
from tests.async_session_adapter import AsyncSessionAdapter


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        yield session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield AsyncSessionAdapter(db_session)

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_password_hashing_behavior(db_session: Session):
    # Verify that verify_password correctly validates and plaintext passwords are never stored
    password = "securePassword123!"
    from app.auth.security import hash_password
    hashed = hash_password(password)
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False


def test_successful_registration(client: TestClient):
    response = client.post(
        "/auth/register",
        json={"email": "register@example.com", "password": "securePassword123!"},
    )
    assert response.status_code == 201
    body = response.json()
    assert "user" in body
    assert "id" in body["user"]
    assert body["user"]["email"] == "register@example.com"
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]


def test_duplicate_email_registration(client: TestClient):
    # Register once
    response1 = client.post(
        "/auth/register",
        json={"email": "duplicate@example.com", "password": "securePassword123!"},
    )
    assert response1.status_code == 201

    # Register again with same email
    response2 = client.post(
        "/auth/register",
        json={"email": "DUPLICATE@example.com", "password": "differentPassword123!"},
    )
    assert response2.status_code == 409
    body = response2.json()
    assert "error" in body
    assert body["error"]["code"] == "CONFLICT"


def test_successful_login(client: TestClient):
    # Register a user
    client.post(
        "/auth/register",
        json={"email": "login@example.com", "password": "securePassword123!"},
    )

    # Login
    response = client.post(
        "/auth/login",
        json={"email": "login@example.com", "password": "securePassword123!"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    
    # Verify that refresh token is set in HttpOnly cookie and not returned in json
    assert "refresh_token" not in body
    assert "refresh_token" in response.cookies


def test_invalid_password_login(client: TestClient):
    client.post(
        "/auth/register",
        json={"email": "wrongpass@example.com", "password": "securePassword123!"},
    )

    response = client.post(
        "/auth/login",
        json={"email": "wrongpass@example.com", "password": "incorrectPassword"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHORIZED"


def test_authenticated_me_route(client: TestClient):
    # Register and login
    client.post(
        "/auth/register",
        json={"email": "me@example.com", "password": "securePassword123!"},
    )
    login_resp = client.post(
        "/auth/login",
        json={"email": "me@example.com", "password": "securePassword123!"},
    )
    access_token = login_resp.json()["access_token"]

    # Call /auth/me with bearer token
    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "user" in body
    assert body["user"]["email"] == "me@example.com"


def test_invalid_access_token(client: TestClient):
    # Request /auth/me with invalid / malformed token
    response1 = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalidtokenhere"},
    )
    assert response1.status_code == 401

    # Request with missing token
    response2 = client.get("/auth/me")
    assert response2.status_code == 401


def test_successful_refresh(client: TestClient):
    # Register and login
    client.post(
        "/auth/register",
        json={"email": "refresh@example.com", "password": "securePassword123!"},
    )
    login_resp = client.post(
        "/auth/login",
        json={"email": "refresh@example.com", "password": "securePassword123!"},
    )
    
    # Call refresh endpoint using refresh token cookie
    refresh_response = client.post("/auth/refresh", cookies=login_resp.cookies)
    assert refresh_response.status_code == 200
    refresh_body = refresh_response.json()
    assert "access_token" in refresh_body
    
    # Ensure new cookie is returned
    assert "refresh_token" in refresh_response.cookies
    assert refresh_response.cookies["refresh_token"] != login_resp.cookies["refresh_token"]


def test_revoked_or_reused_refresh_token(client: TestClient, db_session: Session):
    # Register and login
    client.post(
        "/auth/register",
        json={"email": "reused@example.com", "password": "securePassword123!"},
    )
    login_resp = client.post(
        "/auth/login",
        json={"email": "reused@example.com", "password": "securePassword123!"},
    )
    
    # Save the original refresh token
    orig_cookies = login_resp.cookies
    
    # Use it once to rotate
    refresh_resp1 = client.post("/auth/refresh", cookies=orig_cookies)
    assert refresh_resp1.status_code == 200
    
    # Try to reuse the original refresh token again
    refresh_resp2 = client.post("/auth/refresh", cookies=orig_cookies)
    assert refresh_resp2.status_code == 401
    
    # Check that because of reuse breach detection, all user tokens are now revoked
    user = db_session.query(User).filter_by(email="reused@example.com").first()
    active_tokens = db_session.query(RefreshToken).filter_by(user_id=user.id).filter(RefreshToken.revoked_at.is_(None)).all()
    assert len(active_tokens) == 0


def test_logout(client: TestClient, db_session: Session):
    client.post(
        "/auth/register",
        json={"email": "logout@example.com", "password": "securePassword123!"},
    )
    login_resp = client.post(
        "/auth/login",
        json={"email": "logout@example.com", "password": "securePassword123!"},
    )
    
    # Logout
    logout_resp = client.post("/auth/logout", cookies=login_resp.cookies)
    assert logout_resp.status_code == 204
    
    # Verify cookie is cleared
    assert logout_resp.cookies.get("refresh_token") in (None, "")
    
    # Verify in DB that refresh token is marked revoked
    from app.auth.security import hash_token_sha256
    token_val = login_resp.cookies["refresh_token"]
    token_hash = hash_token_sha256(token_val)
    record = db_session.query(RefreshToken).filter_by(token_hash=token_hash).first()
    assert record is not None
    assert record.revoked_at is not None
