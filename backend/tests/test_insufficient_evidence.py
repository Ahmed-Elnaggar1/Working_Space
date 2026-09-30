from app.bot import INSUFFICIENT_EVIDENCE_THRESHOLD, should_return_insufficient_evidence


def test_should_return_insufficient_evidence_for_low_similarity() -> None:
    ranked_chunks = [(0.05, {"content": "irrelevant"}), (0.02, {"content": "other"})]

    assert should_return_insufficient_evidence(ranked_chunks, threshold=INSUFFICIENT_EVIDENCE_THRESHOLD) is True


def test_should_not_flag_relevant_chunks() -> None:
    ranked_chunks = [(0.71, {"content": "release date is 2027-01-15"}), (0.30, {"content": "other"})]

    assert should_return_insufficient_evidence(ranked_chunks, threshold=INSUFFICIENT_EVIDENCE_THRESHOLD) is False
