from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.bot import generate_answer, search_channel_chunks
from app.bot.schemas import AskRequest, AskResponse
from app.db import get_db
from app.permissions import require_role

router = APIRouter(tags=["bot"])


@router.post(
    "/channels/{channel_id}/ask",
    response_model=AskResponse,
    dependencies=[Depends(require_role("ask_bot"))],
)
def ask_channel(
    channel_id: UUID,
    payload: AskRequest,
    db: Session = Depends(get_db),
) -> dict:
    chunks = search_channel_chunks(db, channel_id, payload.question)
    if not chunks:
        return generate_answer(payload.question, [])

    chunk_context = [
        {
            "id": chunk.id,
            "file_id": chunk.file_id,
            "file_name": chunk.file.filename,
            "page_number": chunk.page_number,
            "content": chunk.content,
        }
        for chunk in chunks
    ]
    return generate_answer(payload.question, chunk_context)
