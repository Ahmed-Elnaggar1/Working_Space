# Sprint 2: Authentication, Workspaces, Channels & Permission Enforcement

**Goal:** Implement the first vertical slice named in the PRD (§14, step 4): signup, login, workspace, channel, membership, and permission enforcement — real working code against the contracts finalized in Sprint 1.

**Sprint outcome:** A new user can sign up, log in, create a workspace and channel, manage channel membership, and every channel-scoped action is authorized server-side according to `docs/security/permissions.md` — with tests proving both the allowed and denied paths.

## Pre-sprint fix

- [ ] Resolve the role-list mismatch between `PRD.md` §6.1 (lists `admin`, `member`, `read_only`) and `PRD.md` §5 / `permissions.md` / `schema.md` / `Architecture.md` (all use `owner`, `admin`, `member`, `read_only`). Update PRD §6.1 to match before implementation starts.

## Stories

| ID | Story | Done when |
|---|---|---|
| S2-01 | Implement `POST /auth/signup` | Password is hashed (never stored plaintext); email uniqueness and lowercase normalization enforced per `schema.md`; test covers success and duplicate-email (`409`). |
| S2-02 | Implement `POST /auth/login` | Returns an access token matching `API.md`'s response shape; test covers success and wrong-password (`401`). |
| S2-03 | Implement `POST /auth/refresh` | Refresh token is rotated on use, the prior token is invalidated, and only `token_hash` is stored, never the raw token; tests cover valid, expired, revoked, and reused-token cases. |
| S2-04 | Build the `get_current_user` auth dependency | Used by every protected route in this sprint; tests cover missing, invalid, and expired token (`401`). |
| S2-05 | Implement `POST /workspaces` | Creates a workspace with `owner_id` set to the caller; test covers success. |
| S2-06 | Implement `POST /workspaces/{workspace_id}/channels` | Enforces the `(workspace_id, name)` uniqueness constraint from `schema.md`; creator receives an `owner` membership in the new channel per `Architecture.md` §5; tests cover success and duplicate-name (`409`). |
| S2-07 | Implement `GET /channels/{channel_id}` | Returns the channel only when the caller has a membership row; resolve and record whether a non-member receives `403` or `404` (see Open Questions) before writing the denial test. |
| S2-08 | Build the central `require_role` dependency in `backend/app/permissions/` | Implements the exact role/action matrix from `permissions.md`; every other module in this sprint calls this dependency, none re-implement a role check, per the ownership rules in `repository-structure.md`. |
| S2-09 | Implement `POST /channels/{channel_id}/members` | Requires `owner` or `admin`; tests cover an allowed role and a `member`/`read_only` denial (`403`). |
| S2-10 | Implement `PATCH /channels/{channel_id}/members/{user_id}` | A role change takes effect on the next authorization check, per the rule in `permissions.md`; test verifies the old role is denied immediately after the change. |
| S2-11 | Implement `DELETE /channels/{channel_id}/members/{user_id}` | Requires `owner` or `admin`; test verifies the removed user is denied access on their next request. |
| S2-12 | Enforce the common error shape | Every `403`, `404`, and `409` response in this sprint matches the error JSON in `API.md`, and never discloses private resource details; test asserts the shape. |
| S2-13 | Write the Sprint 2 Alembic migration | Adds only `users`, `workspaces`, `channels`, `memberships`, and `refresh_tokens` — matching `schema.md`'s constraints and indexes exactly. `files`, `chunks`, and `messages` are deferred to the sprint that implements them, per `Architecture.md` §11. |
| S2-14 | Authorization test matrix | One test per (role × action) pair from `permissions.md`'s table, covering both the allowed and denied outcome for each, per that document's own testing rule. |
| S2-15 | Confirm the CI quality gate on new code | `ruff check` and `pytest` — including the S2-14 matrix — block merge, per the PR checklist in `branching.md`. |

## Open questions to resolve during the sprint

- S2-07: does a non-member requesting a channel that exists receive `403` (channel exists, caller unauthorized) or `404` (existence itself undisclosed)? `permissions.md` allows either depending on whether existence is sensitive — pick one, apply it consistently to all channel-scoped GETs added this sprint, and record the decision as an ADR or a line added to `permissions.md`.

## Out of scope

- File upload and ingestion
- Chat and WebSocket delivery
- Bot / LLM integration
- Frontend implementation
- Production deployment

## Definition of Done

(Unchanged from Sprint 1 — restated here for reference.)

- The change is on a focused branch and reviewed through a pull request.
- Documentation and API behavior agree.
- Automated tests cover new executable behavior.
- Security-sensitive behavior has a negative test, not only a happy-path test.
- `ruff check` and `pytest` pass.
- Any unresolved decision is recorded as an open question or ADR.

## Sprint review checklist

- [ ] A new user can sign up, log in, and receive a working access token end-to-end.
- [ ] A non-member cannot read a channel's data through any endpoint added this sprint (verified manually, not only by unit test).
- [ ] A role change is enforced on the caller's *next* request, not only reflected at the time the membership row is written.
- [ ] Every endpoint added this sprint has both a success test and a denial/error test.
- [ ] The S2-07 open question is resolved and recorded.
- [ ] The Sprint 2 migration matches `schema.md` exactly for the five tables it covers.
- [ ] Next sprint backlog is created from the remaining gaps (files/ingestion, chat, bot).
