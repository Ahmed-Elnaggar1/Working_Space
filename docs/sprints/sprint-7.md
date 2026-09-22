# Sprint 7: Frontend — File Management & Membership Management UI

**Goal:** Let a user upload, view, download, and delete files in a channel, and let an owner/admin manage who's in the channel and with what role — all against real backend endpoints, respecting the same role rules the backend already enforces.

**Sprint outcome:** A member can upload a file and watch its ingestion status resolve (or retry it if it fails), see and download files others have uploaded, and an owner/admin can see the channel's member list, invite someone by email, change a role, or remove a member — with every action's visibility and outcome matching `permissions.md` exactly.

## Epic 0: API Contract Fixes (found while designing this sprint's screens)

| ID | Story | Done when |
|---|---|---|
| S7-01 | Add `GET /channels/{channel_id}/members` | Returns the channel's members with their roles; viewable by any member including `read_only` (record this as the resolved open question below); documented in `API.md`; test covers a member viewing the list and a non-member's denial. |
| S7-02 | Change channel invites to accept an email instead of a `user_id` | `POST /channels/{channel_id}/members` request body changes to `{"email": "...", "role": "member"}`; server resolves the email to a user internally; returns `404` if no account exists with that email, `409` if already a member; `API.md` updated; tests cover success, unknown email, and duplicate-membership cases. |

## Pre-sprint decision

- [ ] **Can the last `owner` remove themselves (or be demoted) from a channel, leaving it ownerless?** Not addressed in `permissions.md`. Recommend blocking this at the API level (return `409` with a clear message) rather than allowing an ownerless channel — decide and implement as part of S7-02's neighboring logic or a small follow-up, before S7-12/S7-13 are built against it.

## Stories

| ID | Story | Done when |
|---|---|---|
| **Epic: File Management UI** ||
| S7-03 | File list view | Uses `GET /channels/{channel_id}/files`; shows filename, uploader, and an ingestion-status badge (`pending`/`processing`/`completed`/`failed`). |
| S7-04 | File upload UI | Calls `POST /channels/{channel_id}/files`; upload control is hidden/disabled for `read_only` members, matching `permissions.md`; shows upload progress; new file appears in S7-03's list without a manual refresh. |
| S7-05 | File download action | Uses the existing download endpoint; triggers a real browser download, not just opening a raw response. |
| S7-06 | Ingestion status polling | While a file's status is `pending` or `processing`, the UI polls (e.g. every few seconds — pick and record an interval) until it settles to `completed` or `failed`, so the badge in S7-03 updates without a manual page refresh. |
| S7-07 | Retry failed ingestion | A retry action appears only on `failed` files, calling the retry endpoint added in Sprint 3 (S3-09); confirms the file's status returns to `pending`/`processing` after retry. |
| S7-08 | File deletion UI | Matches `permissions.md` exactly: a `member` sees a delete action only on files they uploaded; `owner`/`admin` see it on every file; `read_only` sees it on none. |
| **Epic: Membership Management UI** ||
| S7-09 | Member list view | Uses the new `GET /channels/{channel_id}/members` (S7-01); shows each member's email and role. |
| S7-10 | Invite member UI | Calls the updated `POST /channels/{channel_id}/members` (S7-02) by email; visible only to `owner`/`admin`; surfaces the unknown-email (`404`) and already-a-member (`409`) errors clearly rather than a generic failure message. |
| S7-11 | Change member role UI | Calls `PATCH /channels/{channel_id}/members/{user_id}`; visible only to `owner`/`admin`; confirms the change reflects in S7-09's list without a full page reload. |
| S7-12 | Remove member UI | Calls `DELETE /channels/{channel_id}/members/{user_id}`; visible only to `owner`/`admin`; respects the pre-sprint decision on removing the last owner (S7-pre). |
| **Epic: Quality Gate** ||
| S7-13 | Role-based UI visibility matrix | For every action added this sprint (upload, delete-own, delete-any, invite, change-role, remove), confirm the control is shown/hidden/disabled per role exactly as `permissions.md` specifies — and note in the test/PR that this is a UX convenience, not the real security boundary (the backend enforces it regardless, per `Architecture.md` §10). |
| S7-14 | Error-state coverage for new endpoints | `404` (unknown email, file not found), `409` (duplicate membership, last-owner removal), and `403` (role-restricted actions) each have a verified, non-generic UI state. |
| S7-15 | CI gate confirmed for frontend changes this sprint | Lint + build block merge on `main` for this sprint's `frontend/` changes, per `branching.md`. |

## Open questions to resolve during the sprint

- Confirmed as part of S7-01: `read_only` members can view the member list (only mutation actions are role-restricted) — record this explicitly in `permissions.md` since the existing table doesn't cover a "view membership list" action.
- Whether inviting an email with no existing account should create a pending invite (invite-before-signup) — out of scope for v1; the PRD doesn't call for it, and S7-02 simply returns `404` for now. Worth flagging as a deliberate Phase 2 deferral rather than a silent gap.
- Polling interval for ingestion status (S7-06) — pick a concrete number (e.g. 3 seconds) and record it in code comments or `API.md`, rather than leaving it as an arbitrary implementation detail no one remembers choosing.

## Out of scope

- Chat UI and bot/ask UI — Sprint 8
- Real-time (WebSocket-driven) member-list or file-list updates — polling is sufficient for v1
- New file type support beyond what Sprint 3 already ingests
- Invite-before-signup flow (see open questions)

## Definition of Done

- The change is on a focused branch and reviewed through a pull request.
- Documentation (`API.md` for any contract change, `permissions.md` for the S7-01 clarification) and behavior agree.
- Automated tests or a documented manual check cover new behavior.
- Security-sensitive behavior (role-gated actions) has a negative-path check, not only a happy-path one.
- Backend changes pass `ruff check` + `pytest`; frontend changes pass lint + build.
- Any unresolved decision is recorded as an open question or ADR.

## Sprint review checklist

- [ ] A member can upload a file and see its status move from `pending` to `completed` without manually refreshing the page.
- [ ] A failed file shows a retry action, and retrying it works.
- [ ] A `read_only` member sees no upload or delete controls anywhere in the file list.
- [ ] A `member` can delete their own upload but not another member's.
- [ ] An `owner`/`admin` can invite by email, change a role, and remove a member — and a `member`/`read_only` sees none of those controls at all.
- [ ] The last-owner-removal edge case is handled per the pre-sprint decision, not left to fail unpredictably.
- [ ] Every error state in S7-14 has been manually triggered at least once and confirmed correct.
- [ ] Next sprint backlog (chat UI + bot/ask UI) is created from the remaining gaps.
