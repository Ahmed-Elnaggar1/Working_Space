import hashlib
import math

from app.core.config import get_settings


def generate_embedding(text: str, dimension: int | None = None) -> list[float]:
    """Generates a deterministic L2-normalized float vector for a text.
    
    Uses SHA-256 hashing to produce a stable vector of the configured dimension,
    ensuring identical inputs produce identical embeddings without external network dependencies.
    """
    dim = dimension if dimension is not None else get_settings().EMBEDDING_DIMENSION
    normalized_text = " ".join((text or "").strip().split())
    if not normalized_text:
        return [0.0] * dim

    values: list[float] = []
    token = normalized_text.encode("utf-8")
    for i in range(dim):
        digest = hashlib.sha256(token + i.to_bytes(4, byteorder="big", signed=False)).digest()
        raw = int.from_bytes(digest[:8], byteorder="big", signed=False)
        value = ((raw / (2**64 - 1)) * 2.0) - 1.0
        values.append(value)

    norm = math.sqrt(sum(v * v for v in values))
    if norm > 0:
        values = [v / norm for v in values]

    return values

