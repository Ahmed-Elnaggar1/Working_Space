from uuid import UUID

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class Citation(BaseModel):
    file_id: UUID
    file_name: str
    page: int | None


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    insufficient_evidence: bool
