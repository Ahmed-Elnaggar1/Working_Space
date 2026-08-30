from uuid import uuid4

from app.bot.llm import PlaceholderLLMClient, get_llm_api_key, generate_answer


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


def test_llm_api_key_reads_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    assert get_llm_api_key() == "test-key"


def test_placeholder_llm_uses_local_model_name() -> None:
    client = PlaceholderLLMClient()
    assert client.model_name == "placeholder-local-model"
