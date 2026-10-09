import base64
import binascii
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    CurrentUser,
    authenticate_access_token,
    get_current_user,
)
from app.chat.repositories import NotificationRepository
from app.core.db import get_db
from app.models import Notification
from app.notifications.manager import notification_manager
from app.notifications.schemas import (
    MarkAllReadResponse,
    NotificationPage,
    NotificationResponse,
    UnreadCountResponse,
)

router = APIRouter(tags=["notifications"])


def _encode_notification_cursor(notification: Notification) -> str:
    payload = {
        "created_at": notification.created_at.isoformat(),
        "id": str(notification.id),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    )
    return encoded.decode().rstrip("=")


def _decode_notification_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padded_cursor = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded_cursor).decode())
        created_at = datetime.fromisoformat(payload["created_at"])
        notification_id = UUID(payload["id"])
    except (
        KeyError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        binascii.Error,
    ) as error:
        raise HTTPException(
            status_code=400, detail="Invalid notification cursor"
        ) from error

    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at, notification_id


@router.websocket("/ws/notifications")
async def notifications_websocket(websocket: WebSocket) -> None:
    """Per-user real-time notification WebSocket (S11-08)."""
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

    await websocket.accept()
    await notification_manager.connect(current_user.id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await notification_manager.disconnect(current_user.id, websocket)


@router.get(
    "/notifications",
    response_model=NotificationPage,
    status_code=status.HTTP_200_OK,
)
async def get_notifications(
    limit: int = Query(default=50, ge=1, le=100),
    before: str | None = Query(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPage:
    """Paginated, newest-first notifications inbox scoped strictly to the authenticated caller (S11-09)."""
    repo = NotificationRepository(db)
    before_dt = None
    before_id = None
    if before:
        before_dt, before_id = _decode_notification_cursor(before)

    notifications, has_more = await repo.get_user_notifications(
        user_id=current_user.id,
        limit=limit,
        before_created_at=before_dt,
        before_id=before_id,
    )

    next_cursor = (
        _encode_notification_cursor(notifications[-1])
        if (has_more and notifications)
        else None
    )
    return NotificationPage(
        items=[NotificationResponse.model_validate(n) for n in notifications],
        next_cursor=next_cursor,
    )


@router.get(
    "/notifications/unread-count",
    response_model=UnreadCountResponse,
    status_code=status.HTTP_200_OK,
)
async def get_unread_count(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UnreadCountResponse:
    """Computes caller's live unread notifications count (S11-10)."""
    repo = NotificationRepository(db)
    count = await repo.get_unread_count(current_user.id)
    return UnreadCountResponse(unread_count=count)


@router.patch(
    "/notifications/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
)
async def mark_notification_as_read(
    notification_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationResponse:
    """Marks a single notification belonging to the caller as read (S11-11)."""
    repo = NotificationRepository(db)
    notif = await repo.mark_as_read(
        user_id=current_user.id, notification_id=notification_id
    )
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    return NotificationResponse.model_validate(notif)


@router.patch(
    "/notifications/read-all",
    response_model=MarkAllReadResponse,
    status_code=status.HTTP_200_OK,
)
async def mark_all_notifications_as_read(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MarkAllReadResponse:
    """Marks all unread notifications belonging to the caller as read (S11-11)."""
    repo = NotificationRepository(db)
    count = await repo.mark_all_as_read(user_id=current_user.id)
    return MarkAllReadResponse(marked_read_count=count)
