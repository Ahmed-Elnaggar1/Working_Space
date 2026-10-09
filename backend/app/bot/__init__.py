import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.bot.llm import (
    ClaudeClient,
    LLMError,
    LLMServiceError,
    LLMTimeoutError,
    GeminiClient,
    PlaceholderLLMClient,
    build_llm_client,
    generate_answer,
    get_llm_api_key,
)
from app.core.config import get_settings
from app.ingestion.embeddings import generate_embedding
from app.models import Chunk, File

EMBEDDING_MODEL = get_settings().EMBEDDING_MODEL
CHUNK_EMBEDDING_DIMENSION = get_settings().EMBEDDING_DIMENSION
QUESTION_EMBEDDING_DIMENSION = CHUNK_EMBEDDING_DIMENSION
RETRIEVAL_TOP_K = 5
INSUFFICIENT_EVIDENCE_THRESHOLD = 0.3
_RETRIEVAL_STOP_WORDS = {
    "a", "an", "and", "are", "between", "do", "does", "for", "from", "has", "have",
    "how", "in", "is", "it", "many", "much", "of", "on", "or", "the", "to", "what",
    "when", "where", "which", "who", "why", "with",
}


def embed_question(question: str) -> list[float]:
    """Return a deterministic embedding for a user question.

    The vector dimension intentionally matches the chunk embeddings used by the
    retrieval pipeline so channel-scoped similarity search stays compatible.
    """
    return generate_embedding(question, dimension=CHUNK_EMBEDDING_DIMENSION)


def _retrieval_terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in _RETRIEVAL_STOP_WORDS
    }


def _lexical_similarity(question: str, content: str) -> float:
    question_terms = _retrieval_terms(question)
    if len(question_terms) < 2:
        return 0.0
    return len(question_terms & _retrieval_terms(content)) / len(question_terms)


async def search_channel_chunks(
    db: AsyncSession,
    channel_id: UUID,
    question: str,
    limit: int = RETRIEVAL_TOP_K,
    min_score: float | None = None,
) -> list[Chunk]:
    """Return the top-k chunks in a specific channel, ranked by cosine similarity."""
    statement = (
        select(Chunk)
        .options(joinedload(Chunk.file))
        .join(File, Chunk.file_id == File.id)
        .where(Chunk.channel_id == channel_id, File.ingestion_status == "completed")
    )
    chunks = (await db.scalars(statement)).all()

    scored_chunks = []
    for chunk in chunks:
        similarity = _lexical_similarity(question, chunk.content)
        scored_chunks.append((similarity, chunk))

    scored_chunks.sort(key=lambda item: item[0], reverse=True)
    if min_score is not None and should_return_insufficient_evidence(scored_chunks, threshold=min_score):
        return []
    return [chunk for _, chunk in scored_chunks[:limit]]


def should_return_insufficient_evidence(
    ranked_chunks: list[tuple[float, object]],
    threshold: float = INSUFFICIENT_EVIDENCE_THRESHOLD,
) -> bool:
    """Return True when a channel does not contain enough relevant evidence."""
    if not ranked_chunks:
        return True

    best_score = ranked_chunks[0][0]
    return best_score < threshold


__all__ = [
    "EMBEDDING_MODEL",
    "CHUNK_EMBEDDING_DIMENSION",
    "QUESTION_EMBEDDING_DIMENSION",
    "RETRIEVAL_TOP_K",
    "INSUFFICIENT_EVIDENCE_THRESHOLD",
    "ClaudeClient",
    "LLMError",
    "LLMServiceError",
    "LLMTimeoutError",
    "GeminiClient",
    "PlaceholderLLMClient",
    "build_llm_client",
    "embed_question",
    "generate_answer",
    "get_llm_api_key",
    "search_channel_chunks",
    "should_return_insufficient_evidence",
]
