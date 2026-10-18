from functools import lru_cache
import math
from sentence_transformers import SentenceTransformer
from app.core.config import get_settings

@lru_cache(maxsize=1)
def get_embedding_model():
    settings = get_settings()
    # E.g., 'sentence-transformers/all-MiniLM-L6-v2' or 'all-MiniLM-L6-v2'
    model_name = settings.EMBEDDING_MODEL.replace("sentence-transformers/", "")
    return SentenceTransformer(model_name)

def generate_embedding(text: str, dimension: int | None = None) -> list[float]:
    """Generates a semantic embedding vector for a text using SentenceTransformers."""
    settings = get_settings()
    dim = dimension if dimension is not None else settings.EMBEDDING_DIMENSION
    if dim <= 0:
        raise ValueError("Embedding dimension must be a positive integer.")

    normalized_text = " ".join((text or "").strip().split())
    if not normalized_text:
        return [0.0] * dim

    model = get_embedding_model()

    # generate embedding and normalize it (useful for cosine similarity)
    embedding = model.encode(normalized_text, normalize_embeddings=True).tolist()

    if len(embedding) == dim:
        return embedding
    if dim < len(embedding):
        truncated = embedding[:dim]
        norm = math.sqrt(sum(x * x for x in truncated))
        return [x / norm for x in truncated] if norm > 0 else truncated
    return embedding + [0.0] * (dim - len(embedding))

