# Sprint 8: Frontend — Chat UI & Bot/Ask UI

**Goal:** Implement real-time chat and the bot's question-answering UI — the last two frontend feature areas from the PRD's MVP scope.

**Sprint outcome:** A member can send and receive messages in real time within a channel, and any member (including `read_only`) can ask the bot a question and see a grounded, cited answer or an honest "no answer found" state — completing frontend coverage of every MVP feature in the PRD.

## Epic 0: API Contract Fixes (found while designing this sprint's screens)

| ID | Story | Done when |
|---|---|---|
| S8-01 | Specify and implement WebSocket authentication transport | Browsers cannot set custom headers on a WebSocket handshake, so the `Authorization: Bearer` pattern used elsewhere can't apply here. Decide a mechanism — most commonly, the access token passed as a query parameter (`wss://.../ws/channels/{channel_id}?token=...`) — document it explicitly in `API.md`, implement it server-side to match, and confirm token expiry is still checked at connect time. Test covers a valid token connecting and a missing/invalid one being rejected. |
| S8-02 | Resolve `GET /messages` pagination style | Left open in Sprint 5. Decide cursor-based pagination keyed on `created_at`/`id` (works cleanly with a "load older messages" scroll-up pattern, unlike offset pagination which breaks as new messages continuously arrive); document the chosen shape in `API.md`. |

## Stories

| ID | Story | Done when |
|---|---|---|
| **Epic: Chat UI** ||
| S8-03 | Message history view | Initial load via `GET /channels/{channel_id}/messages` using S8-02's pagination; renders oldest-to-newest; supports loading older messages by scrolling up. |
| S8-04 | WebSocket connection lifecycle | Connects using S8-01's auth mechanism when a channel is opened; disconnects when leaving; reconnects automatically on an unexpected drop. |
| S8-05 | Send message UI | Text input, hidden/disabled for `read_only` members per `permissions.md`; sends over the open WebSocket connection when available, falling back to the `POST /messages` REST endpoint if the socket is disconnected, so sending still works even if realtime delivery is temporarily down. |
| S8-06 | Real-time message rendering | Incoming broadcast messages (per Sprint 5's S5-08) are appended to the visible list without a manual refresh; the sender's own just-sent message doesn't appear twice (once optimistically, once from the broadcast echo). |
| **Epic: Bot / Ask UI** ||
| S8-07 | Ask input and submit | Text input + submit calling `POST /channels/{channel_id}/ask`; shows a loading state while waiting, since the LLM call can take a few seconds and there's no streaming (per `Architecture.md` §7). |
| S8-08 | Answer display with citations | Shows the answer text and each citation (`file_name` + `page`); each citation links to the existing file download endpoint so the user can jump to the actual source, not just read a label. |
| S8-09 | Handle `insufficient_evidence` responses | Displays a distinct, honest "no answer found in this channel's materials" state — per Sprint 4's S4-04/S4-07 — rather than showing an empty or awkward response. |
| S8-10 | Handle bot/LLM errors gracefully | Surfaces Sprint 4's S4-08 error shape as a clear, retryable message rather than a generic crash or hang. |
| S8-11 | Session-local ask history | Keeps a running list of this session's question/answer pairs visible on screen; client-side only — the PRD doesn't call for persisting bot Q&A server-side, so this isn't backed by a new table or endpoint. |
| **Epic: Quality Gate** ||
| S8-12 | Role-based visibility for chat and bot | `read_only` members can view messages and ask the bot (per `permissions.md`'s "Ask the bot: Yes" for all roles) but see no send-message input — confirm this exact combination, not just "read-only sees less of everything." |
| S8-13 | Error-state coverage | WebSocket connection rejection (S8-01), `insufficient_evidence` (S8-09), LLM failure (S8-10), and the send-while-disconnected fallback (S8-05) each have a verified, non-generic UI state. |
| S8-14 | End-to-end smoke test | Send/receive a chat message in real time, and ask the bot a question that returns a real cited answer — since this sprint completes frontend coverage of the PRD's entire MVP feature scope (§6), this test is the closest thing to a full MVP walkthrough so far. |
| S8-15 | CI gate confirmed for frontend changes this sprint | Lint + build block merge on `main`, per `branching.md`. |

## Open questions to resolve during the sprint

- Reconnect behavior for S8-04: on reconnect, does the client need to re-fetch recent history to fill any gap while disconnected, or is that an acceptable known limitation for v1? Recommend a simple re-fetch of the latest page on reconnect rather than leaving a silent gap.
- Whether the bot's loading state (S8-07) needs a timeout with a user-facing message if the LLM call runs unusually long — not specified in Sprint 4; a reasonable default (e.g. show a "still working..." note past a few seconds) is worth adding rather than an indefinite spinner.

## Out of scope

- Message editing/deletion, threads, mentions, reactions (explicitly Phase 2 per PRD §7)
- Message streaming / typed-out bot responses
- Persisting bot question/answer history server-side
- Read receipts or typing indicators

## Definition of Done

- The change is on a focused branch and reviewed through a pull request.
- Documentation (`API.md` for the S8-01/S8-02 contract changes) and behavior agree.
- Automated tests or a documented manual check cover new behavior.
- Security-sensitive behavior (WebSocket auth, role-gated send access) has a negative-path check, not only a happy-path one.
- Backend changes pass `ruff check` + `pytest`; frontend changes pass lint + build.
- Any unresolved decision is recorded as an open question or ADR.

## Sprint review checklist

- [x] A member can send a message and see it appear in another connected client in real time.
- [x] A `read_only` member can view messages and ask the bot, but has no way to send a message anywhere in the UI.
- [x] A question with no relevant materials in the channel shows an honest "insufficient evidence" state, not a fabricated-looking answer.
- [x] Every citation shown links back to a real, correct source file.
- [x] Disconnecting and reconnecting the WebSocket doesn't break sending (falls back to REST) or silently lose incoming messages beyond the agreed reconnect behavior.
- [x] With this sprint done, every MVP feature area from the PRD (§6.1–§6.5) now has both a working backend and a working frontend — confirm this directly against the PRD before considering the sprint closed.
- [ ] Next sprint (integration & hardening) backlog is created, informed by anything that felt shaky while building this sprint.
