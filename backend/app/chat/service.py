from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.mentions import extract_mention_usernames, resolve_channel_mentions
from app.chat.repositories import MessageRepository, NotificationRepository
from app.chat.schemas import MessageCreate
from app.models import Mention, Message, Notification
from app.notifications.manager import notification_manager


async def persist_message(
    db: AsyncSession,
    channel_id: UUID,
    user_id: UUID,
    payload: MessageCreate,
) -> Message:
    message_repo = MessageRepository(db)
    notif_repo = NotificationRepository(db)

    # 1. Validate parent message if thread reply
    parent_msg = None
    if payload.parent_message_id:
        parent_msg = await message_repo.get_by_id(payload.parent_message_id)
        if not parent_msg or parent_msg.channel_id != channel_id:
            raise HTTPException(status_code=400, detail="Parent message not found in this channel")
        if parent_msg.parent_message_id is not None:
            raise HTTPException(status_code=400, detail="Nested thread replies are not permitted")

    # 2. Create message
    message = await message_repo.create(
        channel_id=channel_id,
        user_id=user_id,
        content=payload.content,
        parent_message_id=payload.parent_message_id,
    )

    # 3. Handle mentions (S11-03 / S11-04)
    candidate_usernames = extract_mention_usernames(payload.content)
    resolved_mentions = await resolve_channel_mentions(
        db, channel_id, user_id, candidate_usernames
    )
    
    # Track who received a mention notification to avoid duplicate thread notifications
    mentioned_user_ids = set(resolved_mentions.values())
    notifications_to_create = []

    for mentioned_id in mentioned_user_ids:
        db.add(Mention(message_id=message.id, mentioned_user_id=mentioned_id))
        notifications_to_create.append(
            Notification(
                id=uuid4(),
                user_id=mentioned_id,
                actor_id=user_id,
                channel_id=channel_id,
                message_id=message.id,
                type="mention",
                created_at=datetime.now(timezone.utc),
            )
        )

    # 4. Handle thread reply notifications (S11-07)
    if payload.parent_message_id and parent_msg:
        participants = await message_repo.get_thread_participant_ids(parent_msg)
        # Exclude:
        # - The current sender (no self-notifications)
        # - Users already notified via mention in this message
        thread_recipients = participants - {user_id} - mentioned_user_ids

        for recipient_id in thread_recipients:
            notifications_to_create.append(
                Notification(
                    id=uuid4(),
                    user_id=recipient_id,
                    actor_id=user_id,
                    channel_id=channel_id,
                    message_id=message.id,
                    type="thread_reply",
                    created_at=datetime.now(timezone.utc),
                )
            )

    if notifications_to_create:
        notif_repo.add_many(notifications_to_create)

    await db.commit()
    await db.refresh(message)

    # Real-time WebSocket push (S11-08)
    for notif in notifications_to_create:
        notif_payload = {
            "id": str(notif.id),
            "user_id": str(notif.user_id),
            "actor_id": str(notif.actor_id),
            "channel_id": str(notif.channel_id),
            "message_id": str(notif.message_id),
            "type": notif.type,
            "is_read": notif.is_read,
            "created_at": notif.created_at.isoformat(),
        }
        await notification_manager.send_to_user(notif.user_id, notif_payload)

    return message
