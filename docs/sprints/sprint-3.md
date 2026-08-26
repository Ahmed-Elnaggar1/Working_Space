# Sprint 3: Files & Ingestion

**Goal:** Implement file upload/storage/deletion and the ingestion pipeline (parse → chunk → embed), so channel materials become searchable content ready for Sprint 4's bot.

**Sprint outcome:** A member can upload a PDF or text file to a channel, see its ingestion status move from `pending` to `completed` (or a visible, retryable `failed`), and the resulting chunks — with page/section metadata and embeddings — exist in the database, scoped to that channel, ready for retrieval.

## Pre-sprint decision (blocks S3-06 onward)

- [ ] Finalize the embedding model and vector dimension — listed as an open decision in `schema.md` and `Architecture.md` §5. This must be settled before the `chunks.embedding` column and its vector index can be migrated (S3-10) or any chunking/embedding code written (S3-06/S3-07). Record the choice in `schema.md`, replacing the "Open decisions" line.

## Stories

| ID | Story | Done when |
|---|---|---|
| **Epic: File Storage** ||
| S3-01 | Implement `POST /channels/{channel_id}/files` | Requires upload permission per `permissions.md` (`owner`/`admin`/`member`, not `read_only`); stores file bytes in MinIO, creates a `files` row with `ingestion_status = pending`; response never includes raw file content, per `API.md`; tests cover success and denial (`403` for `read_only`). |
| S3-02 | Implement `GET /channels/{channel_id}/files` | Returns files visible to the caller in that channel only; test confirms a non-member gets no results (per S2-07's resolved 403/404 decision). |
| S3-03 | Implement `GET /channels/{channel_id}/files/{file_id}/download` | Verifies both the file's `channel_id` and the caller's membership before streaming, per `API.md`; test covers success and a cross-channel access attempt (file exists, but in a channel the caller isn't a member of). |
| S3-04 | Implement file deletion | Per `permissions.md`: `member` can delete their own upload (`uploaded_by = caller`), `owner`/`admin` can delete any file, `read_only` cannot delete; deleting the metadata row also deletes the MinIO object, per `schema.md`'s deletion policy; tests cover all four role outcomes plus the "member deletes someone else's file" denial case specifically. |
| **Epic: Ingestion Pipeline** ||
| S3-05 | Build the file parser for PDF and plain text | Extracts text preserving page numbers (PDF) or treats the whole file as one section (plain text), per PRD FR2 and `Architecture.md` §7; unit tests cover both file types plus a corrupt/unparseable file case. |
| S3-06 | Build the chunker | Splits parsed text into chunks of a defined size (e.g. ~500 tokens) while keeping each chunk's page/section metadata attached; test confirms no chunk loses its page number. |
| S3-07 | Generate and store embeddings | Each chunk gets an embedding using the model decided in the pre-sprint step, written to `chunks.embedding` with `channel_id` denormalized onto the row (per `Architecture.md` §5 note); test confirms `chunks.channel_id` matches the parent file's channel. |
| S3-08 | Wire ingestion into the upload flow with status transitions | On upload: `pending` → `processing` → `completed`, or `failed` with an actionable error message stored/returned, per PRD FR6 and `Architecture.md` §7 step 1; test covers the full success path and a forced-failure path (e.g. unparseable file). |
| S3-09 | Implement ingestion retry | A `failed` file can be retried without re-uploading, per the PRD's reliability requirement ("failed ingestion must be visible and retryable without silently losing the uploaded file"); decide and implement the retry trigger (e.g. `POST /channels/{channel_id}/files/{file_id}/retry-ingestion`) and add it to `API.md`; test covers retrying a failed file to success. |
| **Epic: Migration & Quality Gate** ||
| S3-10 | Alembic migration for `files` and `chunks` | Matches `schema.md` exactly: `files.channel_id` required, `chunks.file_id` required, `chunks.channel_id` denormalized and required, page/section metadata columns present, vector index added only after S3-embedding-decision dimension is finalized; run against a clean DB and confirm constraints are enforced, not just declared. |
| S3-11 | Authorization test matrix for file actions | One test per (role × action) pair for view/upload/delete-own/delete-any from `permissions.md`'s files rows, both allowed and denied outcomes — same pattern as S2-14. |
| S3-12 | CI gate confirmed on new code | `ruff check` + `pytest` (including S3-11's matrix and the parser/chunker unit tests) block merge on `main`, per `branching.md`. |

## Open questions to resolve during the sprint

- Exact retry endpoint shape and whether retry counts/limits are needed (e.g. stop retrying after N failures) — not specified yet in `API.md` or `schema.md`; decide and document.
- Max file size and accepted MIME types for upload — referenced generally in `Architecture.md` §10 ("uploads validated by type/size") but no concrete limit is set yet.

## Out of scope

- Search bot / RAG query path (retrieval + LLM call) — Sprint 4
- Chat and WebSocket delivery — Sprint 5
- Frontend implementation
- File types beyond PDF and plain text (docx, pptx, images/OCR — explicitly Phase 2 per PRD §7)
- Production object storage (stays on MinIO for local dev this sprint)

## Definition of Done

(Unchanged from Sprint 1/2.)

- The change is on a focused branch and reviewed through a pull request.
- Documentation and API behavior agree.
- Automated tests cover new executable behavior.
- Security-sensitive behavior has a negative test, not only a happy-path test.
- `ruff check` and `pytest` pass.
- Any unresolved decision is recorded as an open question or ADR.

## Sprint review checklist

- [ ] A member can upload a PDF and watch its status move from `pending` to `completed`.
- [ ] A forced-failure upload lands in `failed` with a visible, actionable message — not silently dropped.
- [ ] A failed file can be retried to success without re-uploading.
- [ ] A non-member cannot list, download, or delete files in a channel they don't belong to.
- [ ] A `member` cannot delete another member's uploaded file; a `read_only` member cannot upload or delete at all.
- [ ] Chunks in the database correctly carry page/section metadata and the right `channel_id`.
- [ ] The embedding model/dimension decision is recorded in `schema.md`, replacing the old "open decision" line.
- [ ] Next sprint backlog (bot/RAG query path) is created from the remaining gaps.
