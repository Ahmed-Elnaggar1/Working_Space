from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)
    parent_message_id: UUID | None = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel_id: UUID
    user_id: UUID
    content: str
    parent_message_id: UUID | None = None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()


class MessagePage(BaseModel):
    items: list[MessageResponse]
    next_cursor: str | None = None

class ThreadResponse(BaseModel):
    parent: MessageResponse
    items: list[MessageResponse]
