from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel_id: UUID
    filename: str
    file_name: str = Field(default="")
    storage_path: str
    uploaded_by: UUID
    ingestion_status: str
    ingestion_error: str | None = None
    created_at: datetime

    @model_validator(mode="before")
    @classmethod
    def sync_file_name(cls, data):
        if isinstance(data, dict):
            if "file_name" not in data and "filename" in data:
                data["file_name"] = data["filename"]
            if "filename" not in data and "file_name" in data:
                data["filename"] = data["file_name"]
        return data

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
