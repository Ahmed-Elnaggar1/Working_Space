# Sprint 5: Chat (Messages & WebSocket)

**Goal:** Implement per-channel chat — persisted message history over REST, and real-time delivery over WebSocket — completing the last backend feature area from the PRD's MVP scope.

**Sprint outcome:** A member can send and receive messages in real time within a channel they belong to, message history is retrievable and paginated, and every message — REST or WebSocket — is authorized against the sender's current role, not just checked once at connection time.

## Pre-sprint note

- [ ] This sprint completes backend feature work. If a collaborator is starting frontend in parallel (per the Sprint 4 discussion), Sprint 5's REST endpoints (S5-02/S5-03) are stable early in the sprint and don't need to wait on the WebSocket stories — worth sequencing REST first specifically so frontend isn't blocked longer than necessary.

## Stories

| ID | Story | Done when |
|---|---|---|
| **Epic: Messaging (REST)** ||
| S5-01 | Alembic migration for `messages` | Matches `schema.md` exactly: `channel_id` and `user_id` required, index on `(channel_id, created_at)` for paginated retrieval; run against a clean DB and confirm the constraints are enforced. |
| S5-02 | Implement `POST /channels/{channel_id}/messages` | Requires send-message permission per `permissions.md` (`owner`/`admin`/`member`, not `read_only`); tests cover success and `read_only` denial (`403`). |
| S5-03 | Implement `GET /channels/{channel_id}/messages` | Returns paginated messages ordered by `created_at`, per `API.md`; all four roles can view, per `permissions.md`; test covers pagination behavior and a non-member's denial (per the S2-07 403/404 decision). |
| **Epic: WebSocket Delivery** ||
| S5-04 | Implement `WS /ws/channels/{channel_id}` connection handshake | Requires authentication and channel membership *at connection time*, per `API.md`; test covers a valid member connecting successfully and an invalid token or non-member being rejected during the handshake, not after. |
| S5-05 | Persist WebSocket-sent messages through the same path as REST | A message sent over the WebSocket still creates a `messages` row via the same service logic as S5-02 — one source of truth, not two separate code paths that could drift; test confirms a WS-sent message appears in the `GET /messages` history. |
| S5-06 | Validate every received WebSocket message against the sender's current role | Per `API.md`: "every received message is validated against the sender's role" — this means a role check **per message**, not only once at connection time; test covers a `read_only` connection attempting to send a message after connecting and being rejected. |
| S5-07 | Handle role change or membership removal on an open connection | Per `permissions.md`'s rule that role changes take effect on the next authorization check: for a long-lived WebSocket, decide and implement how that applies — e.g. checking membership fresh on every message (satisfies the rule automatically via S5-06) versus also proactively closing the connection when membership is removed; test covers a user being removed from a channel mid-connection and confirms they can no longer send (and, per your decision, whether the connection is force-closed). |
| S5-08 | Broadcast delivery to connected clients in the same channel | A message from one client is delivered to other currently-connected clients in that same channel, and only that channel; test confirms a client connected to a different channel never receives it. |
| S5-09 | Connection lifecycle handling | Clean disconnect/reconnect behavior, and support for the same user having multiple concurrent connections (e.g. two browser tabs); test covers a normal disconnect not crashing the server and both tabs receiving a broadcast message. |
| **Epic: Quality Gate** ||
| S5-10 | Authorization test matrix for messages | One test per (role × action) pair for view/send from `permissions.md`'s messages rows, both allowed and denied outcomes — same pattern as S2-14/S3-11/S4-10. |
| S5-11 | CI gate confirmed on new code | `ruff check` + `pytest` (including S5-10's matrix and the WebSocket connection/broadcast tests) block merge on `main`, per `branching.md`. |

## Open questions to resolve during the sprint

- Pagination style for `GET /messages` — offset-based or cursor-based? Not yet specified in `API.md`; pick one and document it there.
- Maximum message length — no limit specified yet; needed before `422` validation behavior can be implemented consistently.
- Whether the in-memory connection manager (tracking which sockets belong to which channel) is acceptable for now — this approach only works for a single backend instance, which matches the current modular-monolith/single-container deployment (per `Architecture.md` §9), but is worth explicitly noting as a limitation if the project ever moves to multiple backend instances.
- Message editing/deletion — not in the PRD's MVP scope (§6.3 only mentions "basic per-channel chat/message history"); confirm this stays out of scope for Sprint 5 rather than being added informally.

## Out of scope

- Message editing or deletion
- Threads, mentions, reactions, notifications (explicitly Phase 2 per PRD §7)
- Frontend implementation
- Multi-instance/horizontally-scaled WebSocket delivery

## Definition of Done

(Unchanged from Sprint 1–4.)

- The change is on a focused branch and reviewed through a pull request.
- Documentation and API behavior agree.
- Automated tests cover new executable behavior.
- Security-sensitive behavior has a negative test, not only a happy-path test.
- `ruff check` and `pytest` pass.
- Any unresolved decision is recorded as an open question or ADR.

## Sprint review checklist

- [ ] A member can send a message via WebSocket and see it appear in `GET /messages` history.
- [ ] A `read_only` member cannot send a message via REST or WebSocket.
- [ ] A non-member cannot open a WebSocket connection to a channel they don't belong to.
- [ ] A message sent by a client is only broadcast to other clients connected to the *same* channel.
- [ ] Removing a user's membership mid-connection is enforced on their next send attempt, per the team's S5-07 decision.
- [ ] The pagination and max-message-length open questions are resolved and reflected in `API.md`.
- [ ] With this sprint done, every backend feature area from the PRD's MVP scope (§6) is implemented — confirm this against §6.1–§6.5 directly before calling backend "done."
- [ ] Next sprint backlog (frontend) is created, informed by the now-stable API surface.