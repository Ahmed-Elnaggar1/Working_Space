# Phase 2 Design: File Summarization

**Status:** Design draft — first Phase 2 feature
**Extends:** `Architecture.md` §7 (RAG Pipeline) and §12 ("What This Enables Later")
**Related:** `PRD.md` §7 (previously deferred), `permissions.md`

## 1. What this is

A new bot mode: instead of retrieving top-k relevant chunks for a question, pull **every** chunk belonging to one file and produce a single, coherent summary — with the same citation discipline as Q&A (page/section references), and cached so it isn't regenerated on every view.

## 2. Why this isn't just "the ask endpoint with more chunks"

A file can have far more chunks than fit in one LLM context window. This requires a **map-reduce** summarization strategy:

1. **Map step:** group the file's chunks into batches (e.g. by token budget — say ~3,000 tokens per batch), and summarize each batch independently, with each partial summary noting the page range it covers.
2. **Reduce step:** send all partial summaries (much shorter than the original chunks) to the LLM in one final call, asking it to merge them into one coherent summary that still references page ranges.

This is the same shape as any large-document summarization problem — it scales to files far larger than a single prompt could hold, at the cost of an extra LLM round-trip.

## 3. Caching

A file's summary doesn't change unless the file's ingested content changes. Regenerating it on every view would be needless LLM cost for an identical result. Add:

- `file_summaries` table: `file_id` (FK, unique), `summary_text`, `generated_at`, `model_version`.
- Summaries are generated once (on request) and served from this table thereafter, until explicitly regenerated.

## 4. API additions

```
GET /channels/{channel_id}/files/{file_id}/summary
```
Returns the cached summary if one exists, or a status indicating none has been generated yet (`{"status": "not_generated"}`) — distinct from an error, since "no summary yet" is an expected state, not a failure.

```
POST /channels/{channel_id}/files/{file_id}/summary
```
Triggers generation (or regeneration) of the summary via the map-reduce pipeline above; returns the new summary once complete.

## 5. Permission decision

- **Viewing** a cached summary: same access as viewing the file itself — all four roles (`owner`/`admin`/`member`/`read_only`), per `permissions.md`'s "View files" row.
- **Generating/regenerating** a summary: restricted to `owner`/`admin`/`member` (not `read_only`) — same tier as upload, since it's a cost-incurring action, not a passive read. This mirrors the reasoning already applied to uploads in `permissions.md`.

## 6. Handling files that aren't ready

A file with `ingestion_status` of `pending`, `processing`, or `failed` has no usable chunks yet. `POST .../summary` on such a file returns a clear `409`-style response (e.g. `{"error": {"code": "NOT_READY", ...}}`) rather than attempting to summarize nothing or erroring unhelpfully.

## 7. Open questions to resolve before implementation

- Token-budget-per-batch for the map step — needs a concrete number, similar to Sprint 4's top-k decision.
- Whether summary regeneration should be automatic when a file's ingestion is retried/updated, or always require an explicit regenerate call — recommend explicit-only for now, to keep behavior predictable and avoid surprise LLM costs.
- Whether the reduce step's final LLM call itself needs a fallback if the number of partial summaries is *still* too large for one prompt (very large files) — likely a recursive reduce (summarize the summaries of summaries), worth deciding if you expect files large enough to hit this.
