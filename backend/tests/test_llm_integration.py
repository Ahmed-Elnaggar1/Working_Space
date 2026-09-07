from unittest.mock import MagicMock, patch
from uuid import uuid4

import httpx
import pytest

from app.bot.llm import (
    ClaudeClient,
    LLMServiceError,
    LLMTimeoutError,
    OllamaClient,
    PlaceholderLLMClient,
    build_llm_client,
    generate_answer,
    get_llm_api_key,
)


class MockLLMClient:
    def generate_response(self, question: str, chunks: list[dict]) -> str:
        assert question == "When is the release date?"
        assert chunks[0]["file_name"] == "plan.pdf"
        assert chunks[0]["page_number"] == 4
        return "The release date is 2027-01-15."


def test_generate_answer_uses_context_and_preserves_citations() -> None:
    file_id = uuid4()
    chunk = {
        "id": uuid4(),
        "file_id": file_id,
        "file_name": "plan.pdf",
        "page_number": 4,
        "content": "The release date is 2027-01-15.",
    }

    response = generate_answer(
        "When is the release date?",
        [chunk],
        llm_client=MockLLMClient(),
    )

    assert response["answer"] == "The release date is 2027-01-15."
    assert response["citations"] == [{"file_id": str(file_id), "file_name": "plan.pdf", "page": 4}]
    assert response["insufficient_evidence"] is False


def test_generate_answer_deduplicates_citations_preserving_page_numbers() -> None:
    file_id1 = uuid4()
    file_id2 = uuid4()
    chunks = [
        {"id": uuid4(), "file_id": file_id1, "file_name": "doc1.pdf", "page_number": 2, "content": "Chunk A"},
        {"id": uuid4(), "file_id": file_id1, "file_name": "doc1.pdf", "page_number": 2, "content": "Chunk B (same page)"},
        {"id": uuid4(), "file_id": file_id1, "file_name": "doc1.pdf", "page_number": 5, "content": "Chunk C"},
        {"id": uuid4(), "file_id": file_id2, "file_name": "doc2.pdf", "page_number": 1, "content": "Chunk D"},
    ]

    response = generate_answer(
        "Summarize",
        chunks,
        llm_client=PlaceholderLLMClient(),
    )

    assert response["insufficient_evidence"] is False
    assert len(response["citations"]) == 3
    assert response["citations"] == [
        {"file_id": str(file_id1), "file_name": "doc1.pdf", "page": 2},
        {"file_id": str(file_id1), "file_name": "doc1.pdf", "page": 5},
        {"file_id": str(file_id2), "file_name": "doc2.pdf", "page": 1},
    ]


def test_generate_answer_handles_unpaged_chunks() -> None:
    file_id = uuid4()
    chunks = [
        {"id": uuid4(), "file_id": file_id, "file_name": "notes.txt", "page_number": None, "content": "Notes content"},
    ]

    response = generate_answer(
        "Notes?",
        chunks,
        llm_client=PlaceholderLLMClient(),
    )

    assert response["citations"] == [
        {"file_id": str(file_id), "file_name": "notes.txt", "page": None}
    ]


def test_claude_client_generates_response_on_success() -> None:
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "content": [{"type": "text", "text": "Claude generated answer."}]
    }
    mock_response.raise_for_status.return_value = None

    client = ClaudeClient(api_key="test-api-key")
    chunks = [{"file_id": uuid4(), "file_name": "spec.pdf", "page_number": 1, "content": "Sample content"}]

    with patch("httpx.Client.post", return_value=mock_response) as mock_post:
        result = client.generate_response("What is the spec?", chunks)

    assert result == "Claude generated answer."
    assert mock_post.called


def test_claude_client_timeout_raises_llm_timeout_error() -> None:
    client = ClaudeClient(api_key="test-api-key")
    chunks = [{"file_id": uuid4(), "file_name": "spec.pdf", "page_number": 1, "content": "Sample content"}]

    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Timeout")):
        with pytest.raises(LLMTimeoutError, match="timed out"):
            client.generate_response("Question?", chunks)


def test_claude_client_http_error_raises_llm_service_error() -> None:
    client = ClaudeClient(api_key="test-api-key")
    chunks = [{"file_id": uuid4(), "file_name": "spec.pdf", "page_number": 1, "content": "Sample content"}]

    mock_response = MagicMock()
    mock_response.status_code = 503
    http_err = httpx.HTTPStatusError("503 Service Unavailable", request=MagicMock(), response=mock_response)

    with patch("httpx.Client.post", side_effect=http_err):
        with pytest.raises(LLMServiceError, match="returned status 503"):
            client.generate_response("Question?", chunks)


def test_ollama_client_timeout_raises_llm_timeout_error() -> None:
    client = OllamaClient()
    chunks = [{"file_id": uuid4(), "file_name": "spec.pdf", "page_number": 1, "content": "Sample content"}]

    with patch("httpx.Client.post", side_effect=httpx.TimeoutException("Timeout")):
        with pytest.raises(LLMTimeoutError, match="timed out"):
            client.generate_response("Question?", chunks)


def test_build_llm_client_selection(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "claude")
    assert isinstance(build_llm_client(), ClaudeClient)

    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    assert isinstance(build_llm_client(), ClaudeClient)

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    assert isinstance(build_llm_client(), OllamaClient)

    monkeypatch.setenv("LLM_PROVIDER", "placeholder")
    assert isinstance(build_llm_client(), PlaceholderLLMClient)


def test_llm_api_key_reads_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "claude-key-123")
    assert get_llm_api_key() == "claude-key-123"

    monkeypatch.delenv("ANTHROPIC_API_KEY")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    assert get_llm_api_key() == "test-key"


def test_placeholder_llm_uses_local_model_name() -> None:
    client = PlaceholderLLMClient()
    assert client.model_name == "placeholder-local-model"
