from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class ChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class ChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workspace_id: UUID
    name: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
