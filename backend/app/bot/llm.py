import httpx
import time
from typing import Protocol

from app.core.config import get_settings


INSUFFICIENT_EVIDENCE_MESSAGE = "Insufficient evidence in this channel to answer the question."
SYSTEM_PROMPT = (
    "You are a helpful assistant answering questions based on the provided channel materials and conversation history.\n"
    "Answer questions using only the facts in the provided context or previous messages. "
    "If the context and history do not contain sufficient information to answer a question, say so clearly."
)


class LLMClient(Protocol):
    model_name: str

    def generate_response(self, question: str, chunks: list[dict], history: list[dict] | None = None) -> str:
        ...


def build_context(chunks: list[dict]) -> str:
    return "\n\n".join(
        f"Source: {chunk['file_name']} (page {chunk['page_number']}):\n{chunk['content']}"
        for chunk in chunks
    )


def require_response(text: str, provider: str) -> str:
    answer = text.strip()
    if not answer:
        raise LLMServiceError(f"{provider} returned an empty response.")
    return answer


class LLMError(Exception):
    """Base exception for LLM errors."""


class LLMTimeoutError(LLMError):
    """Raised when an LLM call times out."""


class LLMServiceError(LLMError):
    """Raised when an LLM call fails or returns an error status."""


def _request_with_retries(request):
    settings = get_settings()
    max_attempts = settings.LLM_MAX_RETRIES + 1

    for attempt in range(max_attempts):
        try:
            return request()
        except httpx.TimeoutException as error:
            retryable = True
            last_error = error
        except httpx.RequestError as error:
            retryable = True
            last_error = error
        except httpx.HTTPStatusError as error:
            retryable = error.response.status_code == 429 or error.response.status_code >= 500
            last_error = error

        if not retryable or attempt == max_attempts - 1:
            raise last_error
        time.sleep(settings.LLM_RETRY_DELAY_SECONDS)


class PlaceholderLLMClient:
    """Fallback LLM client for local/test usage without Claude or paid APIs."""

    model_name = "placeholder-local-model"

    def generate_response(self, question: str, chunks: list[dict], history: list[dict] | None = None) -> str:
        if not chunks and not history:
            return INSUFFICIENT_EVIDENCE_MESSAGE

        context = build_context(chunks)
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

    def generate_response(self, question: str, chunks: list[dict], history: list[dict] | None = None) -> str:
        if not chunks and not history:
            return INSUFFICIENT_EVIDENCE_MESSAGE

        messages = []
        if history:
            messages.extend(history)

        if chunks:
            context = build_context(chunks)
            prompt = f"Context:\n{context}\n\nQuestion: {question}"
            messages.append({"role": "user", "content": prompt})
        else:
            messages.append({"role": "user", "content": question})

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model_name,
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": messages,
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = _request_with_retries(
                    lambda: self._post_and_validate(client, headers, payload),
                )
                data = response.json()
                content_blocks = data.get("content", [])
                text_blocks = [
                    block.get("text", "")
                    for block in content_blocks
                    if isinstance(block, dict) and block.get("type") == "text"
                ]
                return require_response("\n".join(text_blocks), "Claude")
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

    def _post_and_validate(self, client: httpx.Client, headers: dict, payload: dict) -> httpx.Response:
        response = client.post(f"{self.base_url}/v1/messages", headers=headers, json=payload)
        response.raise_for_status()
        return response


class GeminiClient:
    """Gemini API client for grounded question answering."""

    def __init__(self, api_key: str | None = None, model: str | None = None, timeout: float = 30.0):
        settings = get_settings()
        self.api_key = api_key or get_llm_api_key()
        self.model_name = model or settings.GEMINI_MODEL
        self.timeout = settings.LLM_TIMEOUT_SECONDS or timeout
        self.base_url = "https://generativelanguage.googleapis.com"

    def generate_response(self, question: str, chunks: list[dict], history: list[dict] | None = None) -> str:
        if not chunks and not history:
            return INSUFFICIENT_EVIDENCE_MESSAGE

        messages = []
        if history:
            for msg in history:
                role = "user" if msg["role"] in ["user", "system"] else "model"
                messages.append({"role": role, "parts": [{"text": msg["content"]}]})

        prompt_text = ""
        if chunks:
            context = build_context(chunks)
            prompt_text = f"Context:\n{context}\n\nQuestion: {question}"
        else:
            prompt_text = question

        messages.append({"role": "user", "parts": [{"text": prompt_text}]})

        payload = {
            "contents": messages,
            "systemInstruction": {
                "role": "user",
                "parts": [{"text": SYSTEM_PROMPT}]
            }
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = _request_with_retries(
                    lambda: self._post_and_validate(client, payload),
                )
                data = response.json()
                try:
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise ValueError("No candidates returned from Gemini.")
                    content = candidates[0]["content"]["parts"][0]["text"]
                except (KeyError, IndexError, TypeError, ValueError) as exc:
                    raise LLMServiceError("Gemini returned an invalid response payload.") from exc
                return require_response(content, "Gemini")
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError("Gemini request timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise LLMServiceError(f"Gemini returned status {exc.response.status_code}.") from exc
        except httpx.RequestError as exc:
            raise LLMServiceError(f"Gemini request failed: {exc}") from exc
        except Exception as exc:
            if isinstance(exc, LLMError):
                raise
            raise LLMServiceError(f"Unexpected Gemini error: {exc}") from exc

    def _post_and_validate(self, client: httpx.Client, payload: dict) -> httpx.Response:
        url = f"{self.base_url}/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        response = client.post(url, json=payload)
        response.raise_for_status()
        return response


def build_llm_client():
    provider = get_settings().LLM_PROVIDER.lower()
    if provider in {"claude", "anthropic"}:
        return ClaudeClient()
    if provider in {"gemini", "google"}:
        return GeminiClient()
    return PlaceholderLLMClient()


def get_llm_api_key() -> str:
    """Read the configured API key from environment, defaulting to a placeholder."""
    settings = get_settings()
    return settings.GEMINI_API_KEY or settings.ANTHROPIC_API_KEY or settings.LLM_API_KEY


def generate_answer(
    question: str,
    chunks: list[dict],
    history: list[dict] | None = None,
    llm_client: LLMClient | None = None,
) -> dict:
    if llm_client is None:
        llm_client = build_llm_client()

    if not chunks and not history:
        return {
            "answer": INSUFFICIENT_EVIDENCE_MESSAGE,
            "citations": [],
            "insufficient_evidence": True,
        }

    for chunk in chunks:
        if "file_name" not in chunk or "page_number" not in chunk:
            raise ValueError("Each chunk must include file metadata and page number.")

    raw_answer = llm_client.generate_response(question, chunks, history)
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
