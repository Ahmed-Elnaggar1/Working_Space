from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, authenticate_access_token, get_current_user
from app.chat.manager import connection_manager
from app.chat.schemas import MessageCreate, MessageResponse
from app.chat.service import persist_message
from app.core.db import get_db
from app.models import Channel, Membership, Message
from app.permissions import require_role
from app.permissions.dependencies import ROLE_PERMISSIONS

router = APIRouter(tags=["chat"])


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
    response_model=list[MessageResponse],
    dependencies=[Depends(require_role("view_messages"))],
)
async def get_messages(
    channel_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[Message]:
    messages = (
        (await db.scalars(
            select(Message)
            .where(Message.channel_id == channel_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .offset(offset)
            .limit(limit)
        ))
        .all()
    )
    return list(messages)
