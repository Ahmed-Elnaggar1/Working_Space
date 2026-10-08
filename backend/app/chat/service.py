from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.chat.mentions import extract_mention_usernames, resolve_channel_mentions
from app.chat.schemas import MessageCreate
from app.models import Mention, Message, Notification

async def persist_message(
    db: AsyncSession,
    channel_id: UUID,
    user_id: UUID,
    payload: MessageCreate,
) -> Message:
    # 1. Create and add the message
    message = Message(
        channel_id=channel_id,
        user_id=user_id,
        content=payload.content,
    )
    db.add(message)
    
    # 2. Flush to populate message.id WITHOUT committing the transaction yet
    await db.flush()

    # 3. Extract candidate usernames from the message content
    candidate_usernames = extract_mention_usernames(payload.content)

    # 4. Resolve candidate usernames against channel memberships
    resolved_mentions = await resolve_channel_mentions(
        db, channel_id, user_id, candidate_usernames
    )

    # 5. Create Mention and Notification rows
    # Since your resolve_channel_mentions returns a dict {username: user_id},
    # we iterate over .values() to get each mentioned user_id:
    for mentioned_user_id in resolved_mentions.values():
        mention = Mention(
            message_id=message.id,
            mentioned_user_id=mentioned_user_id,
        )
        notification = Notification(
            user_id=mentioned_user_id,
            actor_id=user_id,
            channel_id=channel_id,
            message_id=message.id,
            type="mention",
        )
        db.add(mention)
        db.add(notification)

    # 6. Commit the entire transaction atomically (message + mentions + notifications)
    await db.commit()
    await db.refresh(message)
    return message
