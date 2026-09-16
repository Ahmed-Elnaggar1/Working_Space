# Sprint 6: Frontend — Auth & Workspace/Channel Navigation

**Goal:** Stand up the frontend application and implement the first user-facing flows: signup, login, session persistence, and navigating between workspaces and channels.

**Sprint outcome:** A user can sign up, log in, stay logged in across a page refresh, see the workspaces and channels they actually have access to, create new ones, and log out — all against real backend endpoints, with every error state (not just the happy path) handled in the UI.

## Epic 0: API Contract Fixes (found while designing this sprint's screens)

These block frontend work below and should be picked up first, ideally in parallel with S6-05 onward if a collaborator is free to do so.

| ID    | Story                                                | Done when                                                                                                                                                                                                                                                                                                                  |
| ----- | ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S6-01 | Add `GET /workspaces`                                | Returns workspaces the caller owns or has at least one channel membership in (per the join logic already designed); documented in `API.md`; test covers an owner, a channel-member-only user, and an unrelated user (empty result).                                                                                        |
| S6-02 | Add `GET /workspaces/{workspace_id}`                 | Uses a shared access-check (owner or member of any channel in the workspace) so it can never drift from S6-01's logic; documented in `API.md` with the same 403/404 decision as S2-07; test covers access and denial.                                                                                                      |
| S6-03 | Add `GET /workspaces/{workspace_id}/channels`        | Lists **only** the channels within that workspace the caller is a member of — not every channel in the workspace, per the isolation rule in `permissions.md`; documented in `API.md`; test confirms a channel the caller isn't a member of never appears, even though it belongs to a workspace they can otherwise access. |
| S6-04 | Add `refresh_token` to `POST /auth/login`'s response | `API.md`'s login response shape updated to include it; test confirms the returned refresh token is valid at `/auth/refresh`.                                                                                                                                                                                               |
| S6-05 | Add `POST /auth/logout`                              | Revokes the caller's refresh token (`revoked_at` set); documented in `API.md`; test confirms a revoked token is rejected by `/auth/refresh` afterward, not just deleted client-side.                                                                                                                                       |

## Pre-sprint decision

- [ ] **Token storage strategy.** Two realistic options: (a) access token held in memory/React context only, refresh token in an httpOnly cookie set by the backend — more secure, but changes S6-04/S6-05 to set/read a cookie instead of a JSON field; (b) both tokens handled entirely client-side (e.g. in memory, re-fetched via refresh on load) — simpler to build now, weaker against XSS. Pick one before S6-08; if you choose (a), revisit S6-01–S6-05's shapes accordingly before implementing them.

## Stories

| ID                                       | Story                                        | Done when                                                                                                                                                                                                                 |
| ---------------------------------------- | -------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Epic: Frontend Foundation**            |                                              |
| S6-06                                    | Scaffold the React + Vite app in `frontend/` | React Router installed and a base route set up; ESLint/Prettier configured; a frontend CI workflow (lint + build) added per `branching.md`'s PR checklist.                                                                |
| S6-07                                    | Build a shared API client module             | One place that sets the base URL from an environment variable, attaches the `Authorization` header, and parses `API.md`'s common error shape into a usable form — no component fetches directly without going through it. |
| S6-08                                    | Implement the chosen token storage strategy  | Matches the pre-sprint decision; test (or documented manual check) confirms tokens survive a page refresh and are cleared on logout.                                                                                      |
| **Epic: Auth Flows**                     |                                              |
| S6-09                                    | Signup page                                  | Calls `POST /auth/signup`; displays the duplicate-email (`409`) error using the shared error shape, not a raw/generic message.                                                                                            |
| S6-10                                    | Login page                                   | Calls `POST /auth/login`; stores tokens per S6-08; displays wrong-credentials (`401`) clearly; redirects to the workspace list on success.                                                                                |
| S6-11                                    | Session persistence on load                  | On app start, attempts to use a stored refresh token to obtain a fresh access token (via the now-fixed `/auth/refresh`) so the user isn't forced to log in on every visit; falls back to the login page if refresh fails. |
| S6-12                                    | Logout                                       | Calls the new `POST /auth/logout` (S6-05) to revoke the refresh token server-side, then clears local state — not just a local-only clear, per the PRD's revocability requirement.                                         |
| S6-13                                    | Protected route handling                     | Unauthenticated users are redirected to login when visiting any workspace/channel page directly by URL.                                                                                                                   |
| **Epic: Workspace & Channel Navigation** |                                              |
| S6-14                                    | Workspace list/switcher                      | Uses `GET /workspaces` (S6-01); shows only workspaces the current user actually has access to.                                                                                                                            |
| S6-15                                    | Create workspace UI                          | Calls `POST /workspaces`; new workspace appears in S6-14's list without a manual refresh.                                                                                                                                 |
| S6-16                                    | Workspace detail page listing its channels   | Uses `GET /workspaces/{id}` and `GET /workspaces/{id}/channels` (S6-02/S6-03); shows only channels the caller belongs to.                                                                                                 |
| S6-17                                    | Create channel UI                            | Calls `POST /workspaces/{id}/channels`; new channel appears in S6-16's list; surfaces the duplicate-name (`409`) error clearly.                                                                                           |
| S6-18                                    | Channel detail shell page                    | Uses `GET /channels/{id}`; a minimal placeholder page (no files/chat/bot yet — those are Sprint 7/8) that confirms the full navigation path works end to end.                                                             |
| **Epic: Quality Gate**                   |                                              |
| S6-19                                    | Error-state coverage, not just happy paths   | Every error status this sprint's endpoints can return (`401`, `403`, `404`, `409`, `422`) has a corresponding, verified UI state — mirroring the negative-test discipline already applied on the backend.                 |
| S6-20                                    | End-to-end smoke test                        | Signup → login → create workspace → create channel → see it in navigation, either automated or as a documented manual test script if automation tooling isn't set up yet this sprint.                                     |
| S6-21                                    | CI gate confirmed for frontend               | Lint + build block merge on `main` for `frontend/` changes, per `branching.md`.                                                                                                                                           |

## Open questions to resolve during the sprint

- Whether `GET /workspaces/{id}/channels` needs pagination now or can wait — likely fine unpaginated for a small team, but worth a one-line decision in `API.md` rather than leaving it implicit.
- UI convention for showing errors (inline field errors vs. a toast/banner) — not specified anywhere yet; pick one and apply it consistently, same reasoning as the backend's "one documented error shape" rule.

## Out of scope

- File upload/list UI — Sprint 7
- Membership management UI — Sprint 7
- Chat UI and bot/ask UI — Sprint 8
- Visual design polish / mobile responsiveness
- Automated cross-browser testing

## Definition of Done

- The change is on a focused branch and reviewed through a pull request.
- Documentation (`API.md` for any contract change) and behavior agree.
- Automated tests or a documented manual check cover new behavior.
- Security-sensitive behavior (auth, token handling) has a negative-path check, not only a happy-path one.
- Backend changes pass `ruff check` + `pytest`; frontend changes pass lint + build, per each area's own tooling.
- Any unresolved decision is recorded as an open question or ADR.

## Sprint review checklist

- [ ] A new user can sign up, log in, and land on a workspace list showing only their own workspaces.
- [ ] Refreshing the page keeps the user logged in; logging out actually revokes the refresh token server-side, not just locally.
- [ ] A workspace's channel list never shows a channel the current user isn't a member of.
- [ ] Every error case listed in S6-19 has been manually triggered at least once and confirmed to display correctly, not just assumed from the code.
- [x] The three API gaps (Epic 0) are merged and documented in `API.md` before being relied upon by the frontend stories that need them.
- [ ] Next sprint backlog (file upload/list + membership management UI) is created from the remaining gaps.
