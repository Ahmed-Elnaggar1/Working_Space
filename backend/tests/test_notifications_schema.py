import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import Base
from app.models import Channel, Mention, Message, Notification, User, Workspace


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
    yield session
    session.close()


def test_schema_message_parent_and_replies(db_session):
    user = User(email="test@example.com", password_hash="hash")
    workspace = Workspace(name="WS", owner=user)
    channel = Channel(name="general", workspace=workspace)
    db_session.add_all([user, workspace, channel])
    db_session.commit()

    parent = Message(channel_id=channel.id, user_id=user.id, content="Root message")
    db_session.add(parent)
    db_session.commit()

    reply = Message(
        channel_id=channel.id,
        user_id=user.id,
        parent_message_id=parent.id,
        content="Thread reply",
    )
    db_session.add(reply)
    db_session.commit()

    db_session.refresh(parent)
    assert len(parent.replies) == 1
    assert parent.replies[0].id == reply.id
    assert reply.parent.id == parent.id


def test_schema_mentions_unique_constraint(db_session):
    u1 = User(email="u1@example.com", password_hash="hash")
    u2 = User(email="u2@example.com", password_hash="hash")
    workspace = Workspace(name="WS", owner=u1)
    channel = Channel(name="general", workspace=workspace)
    message = Message(channel=channel, user=u1, content="Hello @u2")
    db_session.add_all([u1, u2, workspace, channel, message])
    db_session.commit()

    m1 = Mention(message_id=message.id, mentioned_user_id=u2.id)
    db_session.add(m1)
    db_session.commit()

    # Duplicate mention on same message and user must fail
    m2 = Mention(message_id=message.id, mentioned_user_id=u2.id)
    db_session.add(m2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_schema_notifications_constraints_and_defaults(db_session):
    u1 = User(email="sender@example.com", password_hash="hash")
    u2 = User(email="recipient@example.com", password_hash="hash")
    workspace = Workspace(name="WS", owner=u1)
    channel = Channel(name="general", workspace=workspace)
    message = Message(channel=channel, user=u1, content="Hey")
    db_session.add_all([u1, u2, workspace, channel, message])
    db_session.commit()

    notif = Notification(
        user_id=u2.id,
        actor_id=u1.id,
        channel_id=channel.id,
        message_id=message.id,
        type="mention",
    )
    db_session.add(notif)
    db_session.commit()

    db_session.refresh(notif)
    assert notif.is_read is False
    assert notif.type == "mention"

    # Thread reply type is also valid
    notif_thread = Notification(
        user_id=u2.id,
        actor_id=u1.id,
        channel_id=channel.id,
        message_id=message.id,
        type="thread_reply",
    )
    db_session.add(notif_thread)
    db_session.commit()

    # Invalid type fails CheckConstraint
    notif_invalid = Notification(
        user_id=u2.id,
        actor_id=u1.id,
        channel_id=channel.id,
        message_id=message.id,
        type="invalid_type",
    )
    db_session.add(notif_invalid)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
