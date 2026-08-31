import hashlib
import math
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bot.llm import (
    ClaudeClient,
    LLMError,
    LLMServiceError,
    LLMTimeoutError,
    OllamaClient,
    PlaceholderLLMClient,
    build_llm_client,
    generate_answer,
    get_llm_api_key,
)
from app.models import Chunk, File

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_EMBEDDING_DIMENSION = 384
QUESTION_EMBEDDING_DIMENSION = CHUNK_EMBEDDING_DIMENSION
RETRIEVAL_TOP_K = 5
INSUFFICIENT_EVIDENCE_THRESHOLD = 0.15


def embed_question(question: str) -> list[float]:
    """Return a deterministic embedding for a user question.

    The vector dimension intentionally matches the chunk embeddings used by the
    retrieval pipeline so channel-scoped similarity search stays compatible.
    """
    text = " ".join((question or "").strip().split())
    if not text:
        return [0.0] * CHUNK_EMBEDDING_DIMENSION

    values: list[float] = []
    token = text.encode("utf-8")
    for i in range(CHUNK_EMBEDDING_DIMENSION):
        digest = hashlib.sha256(token + i.to_bytes(4, byteorder="big", signed=False)).digest()
        raw = int.from_bytes(digest[:8], byteorder="big", signed=False)
        value = ((raw / (2**64 - 1)) * 2.0) - 1.0
        values.append(value)

    norm = math.sqrt(sum(value * value for value in values))
    if norm > 0:
        values = [value / norm for value in values]

    return values


def _coerce_vector(values: object) -> list[float]:
    if isinstance(values, str):
        entries = [segment.strip() for segment in values.strip("[] ").split(",") if segment.strip()]
        return [float(value) for value in entries]
    if isinstance(values, (list, tuple)):
        return [float(value) for value in values]
    raise TypeError("Chunk embedding must be stored as a numeric list or JSON array.")


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Embedding dimensions must match for similarity search.")

    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def search_channel_chunks(
    db: Session,
    channel_id: UUID,
    question: str,
    limit: int = RETRIEVAL_TOP_K,
    min_score: float | None = None,
) -> list[Chunk]:
    """Return the top-k chunks in a specific channel, ranked by cosine similarity."""
    query_vector = embed_question(question)
    statement = (
        select(Chunk)
        .join(File, Chunk.file_id == File.id)
        .where(Chunk.channel_id == channel_id, File.ingestion_status == "completed")
    )
    chunks = db.scalars(statement).all()

    scored_chunks = []
    for chunk in chunks:
        chunk_vector = _coerce_vector(chunk.embedding)
        similarity = _cosine_similarity(query_vector, chunk_vector)
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
    "OllamaClient",
    "PlaceholderLLMClient",
    "build_llm_client",
    "embed_question",
    "generate_answer",
    "get_llm_api_key",
    "search_channel_chunks",
    "should_return_insufficient_evidence",
]
