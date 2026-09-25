from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, model_validator
from app.models import Role


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


class MembershipCreate(BaseModel):
    user_id: UUID | None = None
    email: EmailStr | None = None
    role: Role

    @model_validator(mode="after")
    def validate_identity(self):
        has_user_id = self.user_id is not None
        has_email = self.email is not None
        if has_user_id == has_email:
            raise ValueError("Provide exactly one of user_id or email")
        return self


class MembershipUpdate(BaseModel):
    role: Role


class MembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    channel_id: UUID
    role: str


class ChannelMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    email: str
    channel_id: UUID
    role: str

