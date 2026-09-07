from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import CurrentUser, DEV_USER_ID, get_current_user
from app.core import Base, get_db
from app.main import app
from app.models import Channel, Membership, Message, Role, User
from tests.async_session_adapter import AsyncSessionAdapter


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    def override_get_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield AsyncSessionAdapter(session)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=DEV_USER_ID)
    app.state.test_session_factory = session_factory
    app.state.test_engine = engine

    # Ensure dev user exists
    with session_factory() as session:
        user = User(id=DEV_USER_ID, email="dev@example.com", password_hash="hash")
        session.add(user)
        session.commit()

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def create_test_channel(client: TestClient) -> str:
    workspace_res = client.post(
        "/workspaces",
        json={"name": "Engineering"},
    )
    workspace_id = workspace_res.json()["id"]

    channel_res = client.post(
        f"/workspaces/{workspace_id}/channels",
        json={"name": "General"},
    )
    return channel_res.json()["id"]


# --- S5-01: Model and Schema Constraints ---

def test_s5_01_message_constraints_and_cascade(client: TestClient) -> None:
    session_factory = app.state.test_session_factory
    with session_factory() as session:
        # Check index on (channel_id, created_at)
        inspector = inspect(app.state.test_engine)
        indexes = inspector.get_indexes("messages")
        index_cols = [idx["column_names"] for idx in indexes]
        assert ["channel_id", "created_at"] in index_cols

        channel_id = UUID(create_test_channel(client))

        # 1. Null channel_id should fail
        with pytest.raises(IntegrityError):
            session.add(Message(channel_id=None, user_id=DEV_USER_ID, content="hello"))
            session.commit()
        session.rollback()

        # 2. Null user_id should fail
        with pytest.raises(IntegrityError):
            session.add(Message(channel_id=channel_id, user_id=None, content="hello"))
            session.commit()
        session.rollback()

        # 3. Null content should fail
        with pytest.raises(IntegrityError):
            session.add(Message(channel_id=channel_id, user_id=DEV_USER_ID, content=None))
            session.commit()
        session.rollback()

        # 4. Valid message persists
        msg = Message(channel_id=channel_id, user_id=DEV_USER_ID, content="valid message")
        session.add(msg)
        session.commit()
        assert session.query(Message).count() == 1

        # 5. Channel deletion cascades to messages
        channel = session.query(Channel).filter_by(id=channel_id).first()
        session.delete(channel)
        session.commit()
        assert session.query(Message).count() == 0


# --- S5-02: POST /channels/{channel_id}/messages ---

def test_s5_02_send_message_roles(client: TestClient) -> None:
    channel_id = create_test_channel(client)
    session_factory = app.state.test_session_factory

    # Dev user is owner: can send
    res = client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "Hello from owner"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["content"] == "Hello from owner"
    assert data["channel_id"] == channel_id
    assert data["user_id"] == str(DEV_USER_ID)
    assert "id" in data
    assert "created_at" in data

    # Create other users with admin, member, and read_only roles
    roles_and_expected = [
        (Role.ADMIN, 201),
        (Role.MEMBER, 201),
        (Role.READ_ONLY, 403),
    ]

    for role, expected_status in roles_and_expected:
        user_id = uuid4()
        with session_factory() as session:
            session.add(User(id=user_id, email=f"{role.value}@example.com", password_hash="hash"))
            session.add(Membership(user_id=user_id, channel_id=UUID(channel_id), role=role.value))
            session.commit()

        app.dependency_overrides[get_current_user] = lambda u=user_id: CurrentUser(id=u)
        res = client.post(
            f"/channels/{channel_id}/messages",
            json={"content": f"Hello from {role.value}"},
        )
        assert res.status_code == expected_status, f"Role {role.value} got {res.status_code} instead of {expected_status}"


def test_s5_02_send_message_non_member_and_not_found(client: TestClient) -> None:
    channel_id = create_test_channel(client)

    # Non-member
    non_member_id = uuid4()
    with app.state.test_session_factory() as session:
        session.add(User(id=non_member_id, email="nonmember@example.com", password_hash="hash"))
        session.commit()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=non_member_id)
    res = client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "Hello intruder"},
    )
    assert res.status_code == 404

    # Non-existent channel
    res = client.post(
        f"/channels/{uuid4()}/messages",
        json={"content": "Hello nowhere"},
    )
    assert res.status_code == 404


def test_s5_02_send_message_validation(client: TestClient) -> None:
    channel_id = create_test_channel(client)

    # Empty content
    res = client.post(
        f"/channels/{channel_id}/messages",
        json={"content": ""},
    )
    assert res.status_code == 422

    # Missing content
    res = client.post(
        f"/channels/{channel_id}/messages",
        json={},
    )
    assert res.status_code == 422

    # Exceeds max length (4000)
    res = client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "a" * 4001},
    )
    assert res.status_code == 422


# --- S5-03: GET /channels/{channel_id}/messages ---

def test_s5_03_get_messages_all_roles(client: TestClient) -> None:
    channel_id = create_test_channel(client)
    session_factory = app.state.test_session_factory

    # Post a message as owner
    client.post(f"/channels/{channel_id}/messages", json={"content": "Message 1"})

    for role in [Role.OWNER, Role.ADMIN, Role.MEMBER, Role.READ_ONLY]:
        user_id = uuid4() if role != Role.OWNER else DEV_USER_ID
        if role != Role.OWNER:
            with session_factory() as session:
                session.add(User(id=user_id, email=f"view_{role.value}@example.com", password_hash="hash"))
                session.add(Membership(user_id=user_id, channel_id=UUID(channel_id), role=role.value))
                session.commit()

        app.dependency_overrides[get_current_user] = lambda u=user_id: CurrentUser(id=u)
        res = client.get(f"/channels/{channel_id}/messages")
        assert res.status_code == 200, f"Role {role.value} could not view messages: {res.status_code}"
        body = res.json()
        assert len(body) == 1
        assert body[0]["content"] == "Message 1"


def test_s5_03_get_messages_non_member_denial(client: TestClient) -> None:
    channel_id = create_test_channel(client)

    non_member_id = uuid4()
    with app.state.test_session_factory() as session:
        session.add(User(id=non_member_id, email="outsider@example.com", password_hash="hash"))
        session.commit()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=non_member_id)
    res = client.get(f"/channels/{channel_id}/messages")
    assert res.status_code == 404

    # Non-existent channel
    res = client.get(f"/channels/{uuid4()}/messages")
    assert res.status_code == 404


def test_s5_03_get_messages_pagination_and_ordering(client: TestClient) -> None:
    channel_id = create_test_channel(client)
    session_factory = app.state.test_session_factory

    # Create 5 messages with distinct timestamps
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    with session_factory() as session:
        for i in range(5):
            msg = Message(
                channel_id=UUID(channel_id),
                user_id=DEV_USER_ID,
                content=f"Message {i}",
                created_at=base_time + timedelta(minutes=i),
            )
            session.add(msg)
        session.commit()

    # Default pagination (limit=50, offset=0)
    res = client.get(f"/channels/{channel_id}/messages")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 5
    assert [m["content"] for m in items] == [f"Message {i}" for i in range(5)]

    # Limit=2, offset=0
    res = client.get(f"/channels/{channel_id}/messages?limit=2&offset=0")
    assert res.status_code == 200
    page1 = res.json()
    assert len(page1) == 2
    assert [m["content"] for m in page1] == ["Message 0", "Message 1"]

    # Limit=2, offset=2
    res = client.get(f"/channels/{channel_id}/messages?limit=2&offset=2")
    assert res.status_code == 200
    page2 = res.json()
    assert len(page2) == 2
    assert [m["content"] for m in page2] == ["Message 2", "Message 3"]

    # Limit=2, offset=4
    res = client.get(f"/channels/{channel_id}/messages?limit=2&offset=4")
    assert res.status_code == 200
    page3 = res.json()
    assert len(page3) == 1
    assert [m["content"] for m in page3] == ["Message 4"]
