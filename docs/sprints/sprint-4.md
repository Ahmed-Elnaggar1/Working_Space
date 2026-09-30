# Sprint 4: Search Bot (RAG Query Path)

**Goal:** Implement the bot's question-answering path — turn a user's question into a channel-scoped, cited answer, using the chunks and embeddings Sprint 3 produced.

**Sprint outcome:** A member (or read-only member) can ask a question in a channel and get back an answer grounded only in that channel's completed materials, with accurate file/page citations, or an honest "insufficient evidence" response when the channel's materials don't support an answer.

## Pre-sprint check

- [ ] Confirm Sprint 3 actually produced chunks with correct `channel_id` and embeddings for at least one real test document — this sprint has nothing to retrieve against otherwise. If Sprint 3 finished with only synthetic/test data, seed at least one real file through the full ingestion pipeline before starting S4-02.

## Stories

| ID | Story | Done when |
|---|---|---|
| **Epic: Retrieval** ||
| S4-01 | Implement question embedding | The incoming question is embedded using the same model/dimension decided in Sprint 3 — a mismatch here silently breaks similarity search, so add a test asserting the dimension matches `chunks.embedding`. |
| S4-02 | Implement channel-scoped vector similarity search | Query includes `WHERE channel_id = :channel_id` directly in the SQL/ORM query — never fetch broadly and filter after, per `Architecture.md` §6; returns top-k chunks ranked by similarity; test confirms a chunk from another channel never appears in results, even when it would rank higher by similarity alone. |
| S4-03 | Integrate the LLM call (Claude API) | Sends the question plus retrieved chunks (with page numbers) to the LLM, instructed to answer only from the provided chunks and cite them, per `Architecture.md` §7 step 3; `LLM_API_KEY` read from environment, never hardcoded; test uses a mocked LLM response so the test suite doesn't depend on a live API call or incur cost. |
| S4-04 | Implement `insufficient_evidence` handling | When retrieved chunks don't meaningfully support an answer (e.g. similarity scores below a defined threshold, or zero completed chunks in the channel), the response sets `insufficient_evidence: true` per `API.md`'s response shape rather than the LLM guessing; test covers a question with no relevant materials in the channel. |
| S4-05 | Implement `POST /channels/{channel_id}/ask` end to end | Wires S4-01 through S4-04 together behind the existing `require_role` permission dependency; per `permissions.md`, all four roles (`owner`, `admin`, `member`, `read_only`) are allowed to ask — only channel membership is required, no elevated role; test confirms a `read_only` member succeeds and a non-member is denied. |
| S4-06 | Return accurate citations | Response includes `citations: [{file_id, file_name, page}]` matching `API.md`'s shape, and the page numbers returned must match the actual source chunk's `page_number` — not just something the LLM claims in prose; test asserts the returned citation page matches the chunk's stored metadata, not merely that a citation exists. |
| S4-07 | Handle a channel with no completed files gracefully | Asking a question in a channel where no file has finished ingestion (`files.ingestion_status != completed` for all files) returns `insufficient_evidence: true`, not a `500` or an empty crash; test covers a channel with zero files and a channel with only `pending`/`failed` files. |
| S4-08 | Handle LLM call failures | A timeout or error from the Claude API returns a clear, documented error (per `API.md`'s error shape) rather than leaking a raw exception or hanging the request; test simulates an LLM timeout/error and asserts the response shape. |
| **Epic: Accuracy & Quality Gate** ||
| S4-09 | Build a manual QA test set | A defined set of real documents and known-answer questions, per PRD §11's success metric ("90%+ accuracy on a manual QA set"); run the bot against it and record the actual accuracy achieved — this is a manual/documented exercise, not just automated tests. |
| S4-10 | Authorization test matrix for the ask endpoint | One test per role confirming all four roles are allowed (per S4-05) and a non-member is denied — same pattern as S2-14/S3-11, but note this table has only two outcomes (member vs non-member) since `ask` doesn't distinguish `read_only` from the rest. |
| S4-11 | CI gate confirmed on new code | `ruff check` + `pytest` (including S4-10's matrix, S4-03's mocked-LLM test, and S4-02/S4-06/S4-07's retrieval tests) block merge on `main`, per `branching.md`. |

## Open questions to resolve during the sprint

- Exact top-k value for retrieval (how many chunks get sent to the LLM per question) — not yet specified in `Architecture.md`; pick a starting value (e.g. 5) and record it.
- Similarity-score threshold for triggering `insufficient_evidence` (S4-04) — needs a concrete number, not just "low enough."
- Prompt template wording for the LLM call (S4-03) — worth writing down in `Architecture.md` or a new `docs/architecture/prompts.md` once finalized, since it directly affects citation accuracy and is easy to silently drift as it gets tweaked.
- LLM timeout duration and retry behavior (S4-08) — how long to wait before treating a call as failed, and whether to retry once before returning an error to the user.

## Out of scope

- Chat and WebSocket delivery — Sprint 5
- Summarization mode (explicitly Phase 2 per PRD §7)
- Cross-channel search (explicitly Phase 2)
- Frontend implementation
- Production LLM cost controls/rate limiting beyond basic timeout handling

## Definition of Done

(Unchanged from Sprint 1–3.)

- The change is on a focused branch and reviewed through a pull request.
- Documentation and API behavior agree.
- Automated tests cover new executable behavior.
- Security-sensitive behavior has a negative test, not only a happy-path test.
- `ruff check` and `pytest` pass.
- Any unresolved decision is recorded as an open question or ADR.

## Sprint review checklist

- [x] A member can ask a question and get an answer grounded in that channel's materials, with a citation whose page number matches the real source chunk.
- [x] A non-member cannot call the ask endpoint on a channel they don't belong to.
- [x] A question against a channel with no completed files returns `insufficient_evidence: true`, not an error or a hallucinated answer.
- [x] A chunk from another channel never leaks into an answer, verified by an explicit cross-channel test, not just assumed from the query filter.
- [x] The manual QA test set (S4-09) accuracy result is recorded and compared against the PRD's 90% target — and if it falls short, that gap is logged as a known issue, not silently ignored.
- [x] LLM call failures degrade gracefully with a documented error shape.
- [x] Next sprint backlog (chat/WebSocket) is created from the remaining gaps.
