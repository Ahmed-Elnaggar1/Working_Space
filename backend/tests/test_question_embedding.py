from app.bot import CHUNK_EMBEDDING_DIMENSION, EMBEDDING_MODEL, embed_question


def test_question_embedding_matches_chunk_dimension() -> None:
    vector = embed_question("What is the release date?")

    assert len(vector) == CHUNK_EMBEDDING_DIMENSION
    assert EMBEDDING_MODEL == "sentence-transformers/all-MiniLM-L6-v2"
    assert all(isinstance(value, float) for value in vector)
