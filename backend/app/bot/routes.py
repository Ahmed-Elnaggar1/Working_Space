from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot import INSUFFICIENT_EVIDENCE_THRESHOLD, generate_answer, search_channel_chunks
from app.bot.llm import LLMError, LLMServiceError, LLMTimeoutError
from app.bot.schemas import AskRequest, AskResponse
from app.core.db import get_db
from app.permissions import require_role

router = APIRouter(tags=["bot"])


@router.post(
    "/channels/{channel_id}/ask",
    response_model=AskResponse,
    dependencies=[Depends(require_role("ask_bot"))],
)
async def ask_channel(
    channel_id: UUID,
    payload: AskRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    chunks = await search_channel_chunks(
        db,
        channel_id,
        payload.question,
        min_score=INSUFFICIENT_EVIDENCE_THRESHOLD,
    )
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
    try:
        return generate_answer(payload.question, chunk_context)
    except LLMTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=str(exc),
        ) from exc
    except (LLMServiceError, LLMError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
