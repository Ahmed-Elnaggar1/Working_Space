import base64
import binascii
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, authenticate_access_token, get_current_user
from app.chat.manager import connection_manager
from app.chat.schemas import MessageCreate, MessagePage, MessageResponse
from app.chat.service import persist_message
from app.core.db import get_db
from app.models import Channel, Membership, Message
from app.permissions import require_role
from app.permissions.dependencies import ROLE_PERMISSIONS

router = APIRouter(tags=["chat"])


def _encode_message_cursor(message: Message) -> str:
    payload = {"created_at": message.created_at.isoformat(), "id": str(message.id)}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
    return encoded.decode().rstrip("=")


def _decode_message_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padded_cursor = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded_cursor).decode())
        created_at = datetime.fromisoformat(payload["created_at"])
        message_id = UUID(payload["id"])
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError, binascii.Error) as error:
        raise HTTPException(status_code=400, detail="Invalid message cursor") from error

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at, message_id


@router.post(
    "/channels/{channel_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("send_messages"))],
)
async def create_message(
    channel_id: UUID,
    payload: MessageCreate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Message:
    return await persist_message(db, channel_id, current_user.id, payload)


@router.websocket("/ws/channels/{channel_id}")
async def channel_websocket(
    websocket: WebSocket,
    channel_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    token = websocket.query_params.get("token")
    authorization = websocket.headers.get("authorization")
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    if not token:
        await websocket.close(code=1008)
        return

    try:
        current_user = authenticate_access_token(token)
    except HTTPException:
        await websocket.close(code=1008)
        return

    channel_exists = await db.scalar(select(Channel).where(Channel.id == channel_id))
    membership = await db.scalar(
        select(Membership).where(
            Membership.user_id == current_user.id,
            Membership.channel_id == channel_id,
        )
    )
    if not channel_exists or not membership:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await connection_manager.connect(channel_id, websocket)
    try:
        while True:
            data = await websocket.receive_json()
            membership = await db.scalar(
                select(Membership)
                .where(
                    Membership.user_id == current_user.id,
                    Membership.channel_id == channel_id,
                )
                .execution_options(populate_existing=True)
            )
            if not membership:
                await websocket.send_json({"error": "Channel membership is required"})
                await websocket.close(code=1008)
                return

            allowed_actions = ROLE_PERMISSIONS.get(membership.role, set())
            if "send_messages" not in allowed_actions:
                await websocket.send_json({"error": "Permission denied"})
                continue

            try:
                payload = MessageCreate.model_validate(data)
            except ValidationError:
                await websocket.send_json({"error": "Invalid message payload"})
                continue

            message = await persist_message(db, channel_id, current_user.id, payload)
            response = MessageResponse.model_validate(message).model_dump(mode="json")
            await connection_manager.broadcast(channel_id, response, sender=websocket)
    except WebSocketDisconnect:
        return
    finally:
        await connection_manager.disconnect(channel_id, websocket)


@router.get(
    "/channels/{channel_id}/messages",
    response_model=MessagePage,
    dependencies=[Depends(require_role("view_messages"))],
)
async def get_messages(
    channel_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    before: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> MessagePage:
    query = select(Message).where(Message.channel_id == channel_id)
    if before:
        before_created_at, before_id = _decode_message_cursor(before)
        query = query.where(
            or_(
                Message.created_at < before_created_at,
                (Message.created_at == before_created_at) & (Message.id < before_id),
            )
        )

    messages = list((await db.scalars(
        query.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit + 1)
    )).all())
    has_more = len(messages) > limit
    messages = list(reversed(messages[:limit]))
    next_cursor = _encode_message_cursor(messages[0]) if has_more else None
    return MessagePage(items=messages, next_cursor=next_cursor)
