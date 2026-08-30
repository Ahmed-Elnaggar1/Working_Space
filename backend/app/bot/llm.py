import os

import httpx


class PlaceholderLLMClient:
    """Fallback LLM client for local/test usage without Claude or paid APIs."""

    model_name = "placeholder-local-model"

    def generate_response(self, question: str, chunks: list[dict]) -> str:
        if not chunks:
            return "Insufficient evidence in this channel to answer the question."

        context = "\n\n".join(
            f"Source: {chunk['file_name']} (page {chunk['page_number']}):\n{chunk['content']}"
            for chunk in chunks
        )
        return (
            f"Answer based on the provided channel materials.\n\nQuestion: {question}\n\nContext:\n{context}"
        )


class OllamaClient:
    """Local, free LLM provider that exposes an OpenAI-compatible endpoint."""

    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model_name = model or os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct")
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")

    def generate_response(self, question: str, chunks: list[dict]) -> str:
        if not chunks:
            return "Insufficient evidence in this channel to answer the question."

        context = "\n\n".join(
            f"Source: {chunk['file_name']} (page {chunk['page_number']}):\n{chunk['content']}"
            for chunk in chunks
        )
        prompt = (
            "Use only the provided channel materials. Answer the question based on them and "
            "cite the page numbers from the source chunks.\n\n"
            f"Question: {question}\n\nContext:\n{context}"
        )

        response = httpx.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model_name,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["message"]["content"].strip()


def build_llm_client():
    provider = os.getenv("LLM_PROVIDER", "placeholder").lower()
    if provider in {"ollama", "local", "free"}:
        return OllamaClient()
    return PlaceholderLLMClient()


def get_llm_api_key() -> str:
    """Read the configured API key from environment, defaulting to a placeholder."""
    return os.getenv("LLM_API_KEY", "placeholder-local-key")


def generate_answer(question: str, chunks: list[dict], llm_client=None) -> dict:
    if llm_client is None:
        llm_client = build_llm_client()

    if not chunks:
        return {
            "answer": "Insufficient evidence in this channel to answer the question.",
            "citations": [],
            "insufficient_evidence": True,
        }

    for chunk in chunks:
        if "file_name" not in chunk or "page_number" not in chunk:
            raise ValueError("Each chunk must include file metadata and page number.")

    raw_answer = llm_client.generate_response(question, chunks)
    citations = [
        {
            "file_id": str(chunk["file_id"]),
            "file_name": chunk["file_name"],
            "page": chunk["page_number"],
        }
        for chunk in chunks
    ]
    return {
        "answer": raw_answer,
        "citations": citations,
        "insufficient_evidence": False,
    }
