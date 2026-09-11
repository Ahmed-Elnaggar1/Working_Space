import asyncio
from collections import defaultdict
from uuid import UUID

from fastapi import WebSocket


class ChannelConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, channel_id: UUID, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[channel_id].add(websocket)

    async def disconnect(self, channel_id: UUID, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._connections.get(channel_id)
            if not connections:
                return
            connections.discard(websocket)
            if not connections:
                self._connections.pop(channel_id, None)

    async def broadcast(
        self,
        channel_id: UUID,
        payload: dict,
        sender: WebSocket | None = None,
    ) -> None:
        async with self._lock:
            connections = tuple(self._connections.get(channel_id, ()))

        failed_connections: list[WebSocket] = []
        for websocket in connections:
            if websocket is sender:
                continue
            try:
                await websocket.send_json(payload)
            except Exception:
                failed_connections.append(websocket)

        for websocket in failed_connections:
            await self.disconnect(channel_id, websocket)


connection_manager = ChannelConnectionManager()
