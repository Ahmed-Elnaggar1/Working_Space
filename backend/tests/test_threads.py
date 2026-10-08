from collections.abc import Generator
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.dependencies import CurrentUser, DEV_USER_ID, get_current_user
from app.core import Base, get_db
from app.main import app
from app.models import Channel, Membership, Message, Notification, Role, User, Workspace
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

    with session_factory() as session:
        user = User(id=DEV_USER_ID, username="dev_owner", email="owner@example.com", password_hash="hash")
        session.add(user)
        session.commit()

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def setup_channel_and_users(client: TestClient):
    """Sets up a workspace, a channel, and returns IDs for owner, admin, member, read_only, and non_member."""
    session_factory = app.state.test_session_factory

    admin_id = uuid4()
    member_id = uuid4()
    read_only_id = uuid4()
    non_member_id = uuid4()

    workspace_res = client.post("/workspaces", json={"name": "Acme Corp"})
    workspace_id = workspace_res.json()["id"]

    channel_res = client.post(f"/workspaces/{workspace_id}/channels", json={"name": "threads-test"})
    assert channel_res.status_code == 201, f"Failed to create channel: {channel_res.text}"
    channel_id = channel_res.json()["id"]

    with session_factory() as session:
        admin_user = User(id=admin_id, username="admin_user", email="admin@example.com", password_hash="hash")
        member_user = User(id=member_id, username="member_user", email="member@example.com", password_hash="hash")
        ro_user = User(id=read_only_id, username="ro_user", email="ro@example.com", password_hash="hash")
        nm_user = User(id=non_member_id, username="nm_user", email="nonmember@example.com", password_hash="hash")

        session.add_all([admin_user, member_user, ro_user, nm_user])
        session.add_all([
            Membership(user_id=admin_id, channel_id=UUID(channel_id), role="admin"),
            Membership(user_id=member_id, channel_id=UUID(channel_id), role="member"),
            Membership(user_id=read_only_id, channel_id=UUID(channel_id), role="read_only"),
        ])
        session.commit()

    return {
        "workspace_id": workspace_id,
        "channel_id": channel_id,
        "owner_id": DEV_USER_ID,
        "admin_id": admin_id,
        "member_id": member_id,
        "read_only_id": read_only_id,
        "non_member_id": non_member_id,
    }


# ==============================================================================
# S11-05: Implement thread replies (POST /messages with parent_message_id)
# ==============================================================================

def test_s11_05_valid_thread_reply(client: TestClient) -> None:
    ids = setup_channel_and_users(client)
    channel_id = ids["channel_id"]

    # 1. Post a root message
    root_res = client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "Root topic discussion"},
    )
    assert root_res.status_code == 201
    root_id = root_res.json()["id"]

    # 2. Post a thread reply as member
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=ids["member_id"])
    reply_res = client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "Reply to root topic", "parent_message_id": root_id},
    )
    assert reply_res.status_code == 201
    reply_data = reply_res.json()
    assert reply_data["content"] == "Reply to root topic"
    assert reply_data["parent_message_id"] == root_id
    assert reply_data["channel_id"] == channel_id


def test_s11_05_reject_different_channel_parent(client: TestClient) -> None:
    ids = setup_channel_and_users(client)
    channel_1_id = ids["channel_id"]

    # Create channel 2
    ch2_res = client.post(f"/workspaces/{ids['workspace_id']}/channels", json={"name": "random"})
    channel_2_id = ch2_res.json()["id"]

    # Post root in channel 1
    root_res = client.post(f"/channels/{channel_1_id}/messages", json={"content": "Root in ch1"})
    root_id = root_res.json()["id"]

    # Try to reply to channel 1 root from channel 2 -> MUST FAIL 400
    reply_res = client.post(
        f"/channels/{channel_2_id}/messages",
        json={"content": "Sneaky cross-channel reply", "parent_message_id": root_id},
    )
    assert reply_res.status_code == 400
    msg = reply_res.json().get("error", {}).get("message") or reply_res.json().get("detail", "")
    assert "channel" in msg.lower()


def test_s11_05_reject_nested_thread_replies(client: TestClient) -> None:
    ids = setup_channel_and_users(client)
    channel_id = ids["channel_id"]

    # 1. Root message
    root_res = client.post(f"/channels/{channel_id}/messages", json={"content": "Root message"})
    root_id = root_res.json()["id"]

    # 2. Reply 1
    reply_1_res = client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "Level 1 reply", "parent_message_id": root_id},
    )
    assert reply_1_res.status_code == 201
    reply_1_id = reply_1_res.json()["id"]

    # 3. Reply to Reply 1 -> MUST FAIL 400 (flat depth only)
    nested_res = client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "Level 2 nested reply", "parent_message_id": reply_1_id},
    )
    assert nested_res.status_code == 400
    msg = nested_res.json().get("error", {}).get("message") or nested_res.json().get("detail", "")
    assert "nested" in msg.lower()


def test_s11_05_read_only_denial_for_thread_reply(client: TestClient) -> None:
    ids = setup_channel_and_users(client)
    channel_id = ids["channel_id"]

    # Root by owner
    root_res = client.post(f"/channels/{channel_id}/messages", json={"content": "Announcement"})
    root_id = root_res.json()["id"]

    # Read-only user cannot reply
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=ids["read_only_id"])
    reply_res = client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "Can I reply?", "parent_message_id": root_id},
    )
    assert reply_res.status_code == 403


# ==============================================================================
# S11-06: Implement GET .../messages/{message_id}/thread
# ==============================================================================

def test_s11_06_get_thread_replies_ordered(client: TestClient) -> None:
    ids = setup_channel_and_users(client)
    channel_id = ids["channel_id"]

    # Root
    root_res = client.post(f"/channels/{channel_id}/messages", json={"content": "Root"})
    root_id = root_res.json()["id"]

    # Post 2 replies
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=ids["member_id"])
    client.post(f"/channels/{channel_id}/messages", json={"content": "First reply", "parent_message_id": root_id})

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=ids["admin_id"])
    client.post(f"/channels/{channel_id}/messages", json={"content": "Second reply", "parent_message_id": root_id})

    # Read-only user CAN view the thread
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=ids["read_only_id"])
    thread_res = client.get(f"/channels/{channel_id}/messages/{root_id}/thread")
    assert thread_res.status_code == 200

    data = thread_res.json()
    assert data["parent"]["id"] == root_id
    assert data["parent"]["content"] == "Root"
    assert len(data["items"]) == 2
    assert data["items"][0]["content"] == "First reply"
    assert data["items"][1]["content"] == "Second reply"


def test_s11_06_get_thread_non_member_denial_and_not_found(client: TestClient) -> None:
    ids = setup_channel_and_users(client)
    channel_id = ids["channel_id"]

    root_res = client.post(f"/channels/{channel_id}/messages", json={"content": "Root"})
    root_id = root_res.json()["id"]

    # Non-member denied (404 disclosure rule)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=ids["non_member_id"])
    res = client.get(f"/channels/{channel_id}/messages/{root_id}/thread")
    assert res.status_code == 404

    # Non-existent message
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=ids["member_id"])
    res_fake = client.get(f"/channels/{channel_id}/messages/{uuid4()}/thread")
    assert res_fake.status_code == 404


# ==============================================================================
# S11-07: Generate notifications on thread replies
# ==============================================================================

def test_s11_07_thread_notification_recipient_set(client: TestClient) -> None:
    ids = setup_channel_and_users(client)
    channel_id = ids["channel_id"]
    owner_id = ids["owner_id"]
    member_id = ids["member_id"]
    admin_id = ids["admin_id"]
    session_factory = app.state.test_session_factory

    # 1. Alice (owner) posts root message
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=owner_id)
    root_res = client.post(f"/channels/{channel_id}/messages", json={"content": "Alice's Thread"})
    root_id = root_res.json()["id"]

    # 2. Bob (member) replies to Alice's thread
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=member_id)
    client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "Bob's reply", "parent_message_id": root_id},
    )

    # Verify: Alice gets 1 thread_reply notification, Bob gets 0
    with session_factory() as session:
        alice_notifs = list(session.scalars(select(Notification).where(Notification.user_id == owner_id)).all())
        bob_notifs = list(session.scalars(select(Notification).where(Notification.user_id == member_id)).all())
        assert len(alice_notifs) == 1
        assert alice_notifs[0].type == "thread_reply"
        assert alice_notifs[0].actor_id == member_id
        assert len(bob_notifs) == 0

    # 3. Charlie (admin) replies to the thread
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=admin_id)
    client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "Charlie's reply", "parent_message_id": root_id},
    )

    # Verify: Alice (OP) and Bob (prior replier) both receive notification from Charlie; Charlie gets 0
    with session_factory() as session:
        alice_notifs = list(session.scalars(select(Notification).where(Notification.user_id == owner_id)).all())
        bob_notifs = list(session.scalars(select(Notification).where(Notification.user_id == member_id)).all())
        charlie_notifs = list(session.scalars(select(Notification).where(Notification.user_id == admin_id)).all())

        assert len(alice_notifs) == 2
        assert len(bob_notifs) == 1
        assert bob_notifs[0].type == "thread_reply"
        assert bob_notifs[0].actor_id == admin_id
        assert len(charlie_notifs) == 0


def test_s11_07_mention_in_thread_reply_deduplication(client: TestClient) -> None:
    ids = setup_channel_and_users(client)
    channel_id = ids["channel_id"]
    owner_id = ids["owner_id"]
    member_id = ids["member_id"]
    session_factory = app.state.test_session_factory

    # Alice (owner) posts root
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=owner_id)
    root_res = client.post(f"/channels/{channel_id}/messages", json={"content": "Alice's Thread"})
    root_id = root_res.json()["id"]

    # Bob replies and explicitly mentions Alice (@dev_owner)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=member_id)
    client.post(
        f"/channels/{channel_id}/messages",
        json={"content": "Hey @dev_owner replying to you", "parent_message_id": root_id},
    )

    # Verify Alice receives EXACTLY 1 notification (mention takes precedence, no duplicate thread_reply)
    with session_factory() as session:
        alice_notifs = list(session.scalars(select(Notification).where(Notification.user_id == owner_id)).all())
        assert len(alice_notifs) == 1
        assert alice_notifs[0].type == "mention"
