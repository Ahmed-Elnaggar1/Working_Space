import httpx

from app.core.config import get_settings


class LLMError(Exception):
    """Base exception for LLM errors."""


class LLMTimeoutError(LLMError):
    """Raised when an LLM call times out."""


class LLMServiceError(LLMError):
    """Raised when an LLM call fails or returns an error status."""


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


class ClaudeClient:
    """Claude (Anthropic) API client for grounded question answering."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ):
        self.api_key = api_key or get_llm_api_key()
        settings = get_settings()
        self.model_name = model or settings.CLAUDE_MODEL
        self.base_url = (base_url or settings.ANTHROPIC_BASE_URL).rstrip("/")
        self.timeout = settings.LLM_TIMEOUT_SECONDS or timeout

    def generate_response(self, question: str, chunks: list[dict]) -> str:
        if not chunks:
            return "Insufficient evidence in this channel to answer the question."

        context = "\n\n".join(
            f"Source: {chunk['file_name']} (page {chunk['page_number']}):\n{chunk['content']}"
            for chunk in chunks
        )
        prompt = (
            "You are a helpful assistant answering questions strictly based on the provided channel materials.\n"
            "Answer the question using only the facts in the context. Cite the file name and page number for facts.\n"
            "If the context does not contain sufficient information to answer the question, say so clearly.\n\n"
            f"Context:\n{context}\n\n"
            f"Question: {question}"
        )

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/v1/messages",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                content_blocks = data.get("content", [])
                text_blocks = [
                    block.get("text", "")
                    for block in content_blocks
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                return "\n".join(text_blocks).strip()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("Claude API request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise LLMServiceError(f"Claude API returned status {exc.response.status_code}.") from exc
        except httpx.RequestError as exc:
            raise LLMServiceError(f"Claude API request failed: {exc}") from exc
        except Exception as exc:
            if isinstance(exc, LLMError):
                raise
            raise LLMServiceError(f"Unexpected Claude API error: {exc}") from exc


class OllamaClient:
    """Local, free LLM provider that exposes an OpenAI-compatible endpoint."""

    def __init__(self, model: str | None = None, base_url: str | None = None, timeout: float = 120.0):
        settings = get_settings()
        self.model_name = model or settings.OLLAMA_MODEL
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self.timeout = settings.LLM_TIMEOUT_SECONDS or timeout

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

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model_name,
                        "messages": [{"role": "user", "content": prompt}],
                        "stream": False,
                    },
                )
                response.raise_for_status()
                payload = response.json()
                return payload["message"]["content"].strip()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("Ollama request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise LLMServiceError(f"Ollama returned status {exc.response.status_code}.") from exc
        except httpx.RequestError as exc:
            raise LLMServiceError(f"Ollama request failed: {exc}") from exc
        except Exception as exc:
            if isinstance(exc, LLMError):
                raise
            raise LLMServiceError(f"Unexpected Ollama error: {exc}") from exc


def build_llm_client():
    provider = get_settings().LLM_PROVIDER.lower()
    if provider in {"claude", "anthropic"}:
        return ClaudeClient()
    if provider in {"ollama", "local", "free"}:
        return OllamaClient()
    return PlaceholderLLMClient()


def get_llm_api_key() -> str:
    """Read the configured API key from environment, defaulting to a placeholder."""
    settings = get_settings()
    return settings.ANTHROPIC_API_KEY or settings.LLM_API_KEY


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
    seen = set()
    citations = []
    for chunk in chunks:
        file_id = str(chunk["file_id"])
        file_name = chunk["file_name"]
        page = chunk["page_number"]
        key = (file_id, file_name, page)
        if key not in seen:
            seen.add(key)
            citations.append(
                {
                    "file_id": file_id,
                    "file_name": file_name,
                    "page": page,
                }
            )

    return {
        "answer": raw_answer,
        "citations": citations,
        "insufficient_evidence": False,
    }
