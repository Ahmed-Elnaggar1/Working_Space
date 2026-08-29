import hashlib
import numpy as np


def generate_embedding(text: str, dimension: int = 1536) -> list[float]:
    """Generates a deterministic float vector of the specified dimension for a text.
    
    Uses SHA-256 hashing to seed NumPy's default random number generator, producing
    a normalized L2 vector. This ensures identical inputs produce identical embeddings
    with no network dependency.
    """
    if not text:
        return [0.0] * dimension

    # Compute SHA-256 of text
    hash_bytes = hashlib.sha256(text.encode("utf-8")).digest()
    # Convert first 4 bytes of hash to seed integer
    seed = int.from_bytes(hash_bytes[:4], "big")

    # Generate normalized random vector
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(dimension)
    
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm

    return vec.tolist()
