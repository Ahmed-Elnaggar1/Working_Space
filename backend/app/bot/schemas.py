from uuid import UUID

from pydantic import BaseModel, Field


class MessageHistoryItem(BaseModel):
    role: str
    content: str


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: list[MessageHistoryItem] = Field(default_factory=list)


class Citation(BaseModel):
    file_id: UUID
    file_name: str
    page: int | None


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    insufficient_evidence: bool
