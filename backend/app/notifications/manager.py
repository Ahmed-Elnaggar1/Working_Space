import asyncio
from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class NotificationConnectionManager:
    """Manages active per-user WebSocket connections for real-time notification push."""

    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, user_id: UUID, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[user_id].add(websocket)

    async def disconnect(self, user_id: UUID, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._connections.get(user_id)
            if not connections:
                return
            connections.discard(websocket)
            if not connections:
                self._connections.pop(user_id, None)

    async def send_to_user(self, user_id: UUID, payload: dict) -> None:
        """Sends a JSON notification payload to all active WebSockets of a user."""
        async with self._lock:
            connections = tuple(self._connections.get(user_id, ()))

        failed_connections: list[WebSocket] = []
        for websocket in connections:
            try:
                await websocket.send_json(payload)
            except Exception:
                failed_connections.append(websocket)

        for websocket in failed_connections:
            await self.disconnect(user_id, websocket)


notification_manager = NotificationConnectionManager()
