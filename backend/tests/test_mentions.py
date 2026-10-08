import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.chat.mentions import extract_mention_usernames
from app.chat.schemas import MessageCreate
from app.chat.service import persist_message
from app.core import Base
from app.models import Channel, Membership, Mention, Notification, User, Workspace
from tests.async_session_adapter import AsyncSessionAdapter


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield AsyncSessionAdapter(session)
    session.close()


def test_extract_mention_usernames_unit():
    # Basic mention
    assert extract_mention_usernames("Hello @john") == {"john"}

    # Trailing sentence punctuation
    assert extract_mention_usernames("Hey @alice, check @bob. Are you there @sara?!") == {
        "alice",
        "bob",
        "sara",
    }

    # Case insensitivity & deduplication
    assert extract_mention_usernames("@Alex and @alex and @ALEX") == {"alex"}

    # Underscores and dashes preserved
    assert extract_mention_usernames("Call @john_doe and @jane-doe") == {
        "john_doe",
        "jane-doe",
    }

    # Emails should not be parsed as mentions
    assert extract_mention_usernames("Contact us at support@example.com") == set()
    assert extract_mention_usernames("Write to test@company.org and cc @valid_user") == {
        "valid_user"
    }


@pytest.mark.anyio
async def test_valid_mention_generates_mention_and_notification(db_session):
    alice = User(username="alice", email="alice@example.com", password_hash="hash")
    bob = User(username="bob", email="bob@example.com", password_hash="hash")
    workspace = Workspace(name="WS", owner=alice)
    channel = Channel(name="dev", workspace=workspace)

    db_session.add_all([alice, bob, workspace, channel])
    await db_session.commit()

    mem_alice = Membership(user_id=alice.id, channel_id=channel.id, role="owner")
    mem_bob = Membership(user_id=bob.id, channel_id=channel.id, role="member")
    db_session.add_all([mem_alice, mem_bob])
    await db_session.commit()

    payload = MessageCreate(content="Hey @bob check out this feature!")
    msg = await persist_message(db_session, channel.id, alice.id, payload)

    assert msg.id is not None

    # Check Mention record
    mentions_stmt = select(Mention).where(Mention.message_id == msg.id)
    mentions = list((await db_session.scalars(mentions_stmt)).all())
    assert len(mentions) == 1
    assert mentions[0].mentioned_user_id == bob.id

    # Check Notification record
    notifs_stmt = select(Notification).where(Notification.message_id == msg.id)
    notifs = list((await db_session.scalars(notifs_stmt)).all())
    assert len(notifs) == 1
    assert notifs[0].user_id == bob.id
    assert notifs[0].actor_id == alice.id
    assert notifs[0].channel_id == channel.id
    assert notifs[0].type == "mention"
    assert notifs[0].is_read is False


@pytest.mark.anyio
async def test_non_member_mention_is_ignored(db_session):
    alice = User(username="alice", email="alice@example.com", password_hash="hash")
    charlie = User(username="charlie", email="charlie@example.com", password_hash="hash")
    workspace = Workspace(name="WS", owner=alice)
    channel = Channel(name="dev", workspace=workspace)

    db_session.add_all([alice, charlie, workspace, channel])
    await db_session.commit()

    mem_alice = Membership(user_id=alice.id, channel_id=channel.id, role="owner")
    # Charlie is NOT a member of channel
    db_session.add(mem_alice)
    await db_session.commit()

    payload = MessageCreate(content="Hey @charlie and @unknown_user, are you here?")
    msg = await persist_message(db_session, channel.id, alice.id, payload)

    # No mentions and no notifications should be generated
    mentions = list(
        (await db_session.scalars(select(Mention).where(Mention.message_id == msg.id))).all()
    )
    assert len(mentions) == 0

    notifs = list(
        (await db_session.scalars(select(Notification).where(Notification.message_id == msg.id))).all()
    )
    assert len(notifs) == 0


@pytest.mark.anyio
async def test_read_only_member_can_be_mentioned(db_session):
    alice = User(username="alice", email="alice@example.com", password_hash="hash")
    sara = User(username="sara", email="sara@example.com", password_hash="hash")
    workspace = Workspace(name="WS", owner=alice)
    channel = Channel(name="announcements", workspace=workspace)

    db_session.add_all([alice, sara, workspace, channel])
    await db_session.commit()

    mem_alice = Membership(user_id=alice.id, channel_id=channel.id, role="owner")
    mem_sara = Membership(user_id=sara.id, channel_id=channel.id, role="read_only")
    db_session.add_all([mem_alice, mem_sara])
    await db_session.commit()

    payload = MessageCreate(content="FYI @sara please see this announcement")
    msg = await persist_message(db_session, channel.id, alice.id, payload)

    mentions = list(
        (await db_session.scalars(select(Mention).where(Mention.message_id == msg.id))).all()
    )
    assert len(mentions) == 1
    assert mentions[0].mentioned_user_id == sara.id

    notifs = list(
        (await db_session.scalars(select(Notification).where(Notification.message_id == msg.id))).all()
    )
    assert len(notifs) == 1
    assert notifs[0].user_id == sara.id


@pytest.mark.anyio
async def test_self_mention_is_ignored(db_session):
    alice = User(username="alice", email="alice@example.com", password_hash="hash")
    workspace = Workspace(name="WS", owner=alice)
    channel = Channel(name="dev", workspace=workspace)

    db_session.add_all([alice, workspace, channel])
    await db_session.commit()

    mem_alice = Membership(user_id=alice.id, channel_id=channel.id, role="owner")
    db_session.add(mem_alice)
    await db_session.commit()

    payload = MessageCreate(content="Note to self: @alice deploy to production")
    msg = await persist_message(db_session, channel.id, alice.id, payload)

    mentions = list(
        (await db_session.scalars(select(Mention).where(Mention.message_id == msg.id))).all()
    )
    assert len(mentions) == 0

    notifs = list(
        (await db_session.scalars(select(Notification).where(Notification.message_id == msg.id))).all()
    )
    assert len(notifs) == 0


@pytest.mark.anyio
async def test_duplicate_mentions_in_single_message_are_deduplicated(db_session):
    alice = User(username="alice", email="alice@example.com", password_hash="hash")
    bob = User(username="bob", email="bob@example.com", password_hash="hash")
    workspace = Workspace(name="WS", owner=alice)
    channel = Channel(name="dev", workspace=workspace)

    db_session.add_all([alice, bob, workspace, channel])
    await db_session.commit()

    mem_alice = Membership(user_id=alice.id, channel_id=channel.id, role="owner")
    mem_bob = Membership(user_id=bob.id, channel_id=channel.id, role="member")
    db_session.add_all([mem_alice, mem_bob])
    await db_session.commit()

    payload = MessageCreate(content="Attention @bob! Repeating @BOB and @bob again!")
    msg = await persist_message(db_session, channel.id, alice.id, payload)

    mentions = list(
        (await db_session.scalars(select(Mention).where(Mention.message_id == msg.id))).all()
    )
    assert len(mentions) == 1
    assert mentions[0].mentioned_user_id == bob.id

    notifs = list(
        (await db_session.scalars(select(Notification).where(Notification.message_id == msg.id))).all()
    )
    assert len(notifs) == 1
    assert notifs[0].user_id == bob.id
