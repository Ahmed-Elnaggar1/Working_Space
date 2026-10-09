from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.websockets import WebSocketDisconnect

from app.auth.dependencies import CurrentUser, get_current_user
from app.auth.security import create_access_token
from app.core import Base
from app.core.db import get_db
from app.main import app
from app.models import Membership, Notification, User
from tests.async_session_adapter import AsyncSessionAdapter

DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture
def anyio_backend():
    return "asyncio"


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

    with session_factory() as session:
        user = User(
            id=DEV_USER_ID,
            username="dev_owner",
            email="owner@example.com",
            password_hash="hash",
        )
        session.add(user)
        session.commit()

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def setup_users_and_channel(client: TestClient):
    """Sets up channel and Alice/Bob users for testing notifications."""
    session_factory = app.state.test_session_factory

    alice_id = uuid4()
    bob_id = uuid4()

    workspace_res = client.post("/workspaces", json={"name": "Test Workspace"})
    workspace_id = workspace_res.json()["id"]

    channel_res = client.post(
        f"/workspaces/{workspace_id}/channels", json={"name": "notif-test"}
    )
    channel_id = channel_res.json()["id"]

    with session_factory() as session:
        alice = User(
            id=alice_id,
            username="alice",
            email="alice@example.com",
            password_hash="hash",
        )
        bob = User(
            id=bob_id,
            username="bob",
            email="bob@example.com",
            password_hash="hash",
        )
        session.add_all([alice, bob])
        session.add_all([
            Membership(
                user_id=alice_id, channel_id=UUID(channel_id), role="member"
            ),
            Membership(
                user_id=bob_id, channel_id=UUID(channel_id), role="member"
            ),
        ])
        session.commit()

    return {
        "workspace_id": workspace_id,
        "channel_id": channel_id,
        "alice_id": alice_id,
        "bob_id": bob_id,
    }


# ==============================================================================
# S11-08: WebSocket /ws/notifications
# ==============================================================================


def test_s11_08_ws_notifications_reject_missing_and_invalid_token(
    client: TestClient,
) -> None:
    # 1. Missing token -> 1008
    with pytest.raises(WebSocketDisconnect) as err:
        with client.websocket_connect("/ws/notifications"):
            pass
    assert err.value.code == 1008

    # 2. Invalid token -> 1008
    with pytest.raises(WebSocketDisconnect) as err:
        with client.websocket_connect("/ws/notifications?token=invalid.jwt.token"):
            pass
    assert err.value.code == 1008


def test_s11_08_ws_notifications_realtime_push_on_mention(
    client: TestClient,
) -> None:
    data = setup_users_and_channel(client)
    alice_id = data["alice_id"]
    bob_id = data["bob_id"]
    channel_id = data["channel_id"]

    alice_token = create_access_token(alice_id)

    # Alice connects to her notification websocket
    with client.websocket_connect(
        f"/ws/notifications?token={alice_token}"
    ) as alice_ws:
        # Bob posts a message mentioning @alice
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id=bob_id
        )
        msg_res = client.post(
            f"/channels/{channel_id}/messages",
            json={"content": "Hey @alice check this out!"},
        )
        assert msg_res.status_code == 201

        # Alice should receive real-time notification push
        notif_data = alice_ws.receive_json()
        assert notif_data["type"] == "mention"
        assert notif_data["user_id"] == str(alice_id)
        assert notif_data["actor_id"] == str(bob_id)
        assert notif_data["channel_id"] == channel_id
        assert notif_data["is_read"] is False


def test_s11_08_ws_notifications_realtime_push_on_thread_reply(
    client: TestClient,
) -> None:
    data = setup_users_and_channel(client)
    alice_id = data["alice_id"]
    bob_id = data["bob_id"]
    channel_id = data["channel_id"]

    # 1. Alice creates root thread message
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=alice_id)
    root_res = client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "Alice's original discussion"},
    )
    root_id = root_res.json()["id"]

    alice_token = create_access_token(alice_id)

    # 2. Alice connects to notification websocket
    with client.websocket_connect(
        f"/ws/notifications?token={alice_token}"
    ) as alice_ws:
        # 3. Bob posts a thread reply
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(
            id=bob_id
        )
        reply_res = client.post(
            f"/channels/{channel_id}/messages",
            json={
                "content": "Bob replying to Alice",
                "parent_message_id": root_id,
            },
        )
        assert reply_res.status_code == 201

        # Alice receives real-time thread_reply push
        notif_data = alice_ws.receive_json()
        assert notif_data["type"] == "thread_reply"
        assert notif_data["user_id"] == str(alice_id)
        assert notif_data["actor_id"] == str(bob_id)
        assert notif_data["is_read"] is False


# ==============================================================================
# S11-09: GET /notifications (Inbox & Pagination)
# ==============================================================================


def test_s11_09_get_notifications_empty(client: TestClient) -> None:
    data = setup_users_and_channel(client)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=data["alice_id"]
    )

    res = client.get("/notifications")
    assert res.status_code == 200
    body = res.json()
    assert body["items"] == []
    assert body["next_cursor"] is None


def test_s11_09_get_notifications_newest_first_and_pagination(
    client: TestClient,
) -> None:
    data = setup_users_and_channel(client)
    alice_id = data["alice_id"]
    bob_id = data["bob_id"]
    channel_id = UUID(data["channel_id"])
    session_factory = app.state.test_session_factory

    base_time = datetime.now(timezone.utc)
    # Insert 3 notifications for Alice at different times
    with session_factory() as session:
        msg_id = uuid4()
        n1_id = uuid4()
        n1 = Notification(
            id=n1_id,
            user_id=alice_id,
            actor_id=bob_id,
            channel_id=channel_id,
            message_id=msg_id,
            type="mention",
            is_read=False,
            created_at=base_time - timedelta(minutes=10),
        )
        n2 = Notification(
            id=uuid4(),
            user_id=alice_id,
            actor_id=bob_id,
            channel_id=channel_id,
            message_id=msg_id,
            type="thread_reply",
            is_read=False,
            created_at=base_time - timedelta(minutes=5),
        )
        n3 = Notification(
            id=uuid4(),
            user_id=alice_id,
            actor_id=bob_id,
            channel_id=channel_id,
            message_id=msg_id,
            type="mention",
            is_read=False,
            created_at=base_time,
        )
        session.add_all([n1, n2, n3])
        session.commit()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=alice_id)

    # 1. Fetch page with limit 2 -> newest first (n3, then n2)
    res_p1 = client.get("/notifications?limit=2")
    assert res_p1.status_code == 200
    p1 = res_p1.json()
    assert len(p1["items"]) == 2
    assert p1["items"][0]["type"] == "mention"
    assert p1["items"][1]["type"] == "thread_reply"
    cursor = p1["next_cursor"]
    assert cursor is not None

    # 2. Fetch page 2 using cursor -> should return n1
    res_p2 = client.get(f"/notifications?limit=2&before={cursor}")
    assert res_p2.status_code == 200
    p2 = res_p2.json()
    assert len(p2["items"]) == 1
    assert p2["items"][0]["id"] == str(n1_id)
    assert p2["next_cursor"] is None


def test_s11_09_get_notifications_caller_isolation(client: TestClient) -> None:
    data = setup_users_and_channel(client)
    alice_id = data["alice_id"]
    bob_id = data["bob_id"]
    session_factory = app.state.test_session_factory

    with session_factory() as session:
        session.add(
            Notification(
                id=uuid4(),
                user_id=alice_id,
                actor_id=bob_id,
                channel_id=UUID(data["channel_id"]),
                message_id=uuid4(),
                type="mention",
                is_read=False,
            )
        )
        session.commit()

    # Bob's inbox should be completely empty (no leak of Alice's notification)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=bob_id)
    res = client.get("/notifications")
    assert res.status_code == 200
    assert res.json()["items"] == []


# ==============================================================================
# S11-10: GET /notifications/unread-count
# ==============================================================================


def test_s11_10_unread_count_live_computation(client: TestClient) -> None:
    data = setup_users_and_channel(client)
    alice_id = data["alice_id"]
    bob_id = data["bob_id"]
    session_factory = app.state.test_session_factory

    with session_factory() as session:
        n1 = Notification(
            id=uuid4(),
            user_id=alice_id,
            actor_id=bob_id,
            channel_id=UUID(data["channel_id"]),
            message_id=uuid4(),
            type="mention",
            is_read=False,
        )
        n2 = Notification(
            id=uuid4(),
            user_id=alice_id,
            actor_id=bob_id,
            channel_id=UUID(data["channel_id"]),
            message_id=uuid4(),
            type="thread_reply",
            is_read=False,
        )
        n3 = Notification(
            id=uuid4(),
            user_id=alice_id,
            actor_id=bob_id,
            channel_id=UUID(data["channel_id"]),
            message_id=uuid4(),
            type="mention",
            is_read=True,  # Already read
        )
        session.add_all([n1, n2, n3])
        session.commit()

    # Alice should have unread count = 2
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=alice_id)
    res = client.get("/notifications/unread-count")
    assert res.status_code == 200
    assert res.json()["unread_count"] == 2

    # Bob should have unread count = 0
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=bob_id)
    res_bob = client.get("/notifications/unread-count")
    assert res_bob.status_code == 200
    assert res_bob.json()["unread_count"] == 0


# ==============================================================================
# S11-11: PATCH /notifications/{id}/read & PATCH /notifications/read-all
# ==============================================================================


def test_s11_11_mark_single_notification_as_read(client: TestClient) -> None:
    data = setup_users_and_channel(client)
    alice_id = data["alice_id"]
    session_factory = app.state.test_session_factory

    notif_id = uuid4()
    with session_factory() as session:
        session.add(
            Notification(
                id=notif_id,
                user_id=alice_id,
                actor_id=data["bob_id"],
                channel_id=UUID(data["channel_id"]),
                message_id=uuid4(),
                type="mention",
                is_read=False,
            )
        )
        session.commit()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=alice_id)

    # Mark as read
    res = client.patch(f"/notifications/{notif_id}/read")
    assert res.status_code == 200
    assert res.json()["is_read"] is True

    # Check unread count is now 0
    cnt_res = client.get("/notifications/unread-count")
    assert cnt_res.json()["unread_count"] == 0


def test_s11_11_mark_read_cross_user_denial(client: TestClient) -> None:
    data = setup_users_and_channel(client)
    alice_id = data["alice_id"]
    bob_id = data["bob_id"]
    session_factory = app.state.test_session_factory

    alice_notif_id = uuid4()
    with session_factory() as session:
        session.add(
            Notification(
                id=alice_notif_id,
                user_id=alice_id,
                actor_id=bob_id,
                channel_id=UUID(data["channel_id"]),
                message_id=uuid4(),
                type="mention",
                is_read=False,
            )
        )
        session.commit()

    # Bob attempts to mark Alice's notification as read -> MUST return 404
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=bob_id)
    res = client.patch(f"/notifications/{alice_notif_id}/read")
    assert res.status_code == 404

    # Alice's notification remains unread
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=alice_id)
    cnt_res = client.get("/notifications/unread-count")
    assert cnt_res.json()["unread_count"] == 1


def test_s11_11_mark_all_notifications_as_read(client: TestClient) -> None:
    data = setup_users_and_channel(client)
    alice_id = data["alice_id"]
    session_factory = app.state.test_session_factory

    with session_factory() as session:
        n1 = Notification(
            id=uuid4(),
            user_id=alice_id,
            actor_id=data["bob_id"],
            channel_id=UUID(data["channel_id"]),
            message_id=uuid4(),
            type="mention",
            is_read=False,
        )
        n2 = Notification(
            id=uuid4(),
            user_id=alice_id,
            actor_id=data["bob_id"],
            channel_id=UUID(data["channel_id"]),
            message_id=uuid4(),
            type="thread_reply",
            is_read=False,
        )
        session.add_all([n1, n2])
        session.commit()

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=alice_id)

    # Mark all read
    res = client.patch("/notifications/read-all")
    assert res.status_code == 200
    assert res.json()["marked_read_count"] == 2

    # Verify unread count is 0
    cnt_res = client.get("/notifications/unread-count")
    assert cnt_res.json()["unread_count"] == 0

    # Calling mark-all again returns marked_read_count = 0
    res2 = client.patch("/notifications/read-all")
    assert res2.status_code == 200
    assert res2.json()["marked_read_count"] == 0
