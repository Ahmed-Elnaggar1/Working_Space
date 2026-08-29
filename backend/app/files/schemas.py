from datetime import datetime, timezone
from uuid import UUID
from pydantic import BaseModel, ConfigDict, field_serializer


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel_id: UUID
    filename: str
    storage_path: str
    uploaded_by: UUID
    ingestion_status: str
    ingestion_error: str | None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
