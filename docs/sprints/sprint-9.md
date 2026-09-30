# Sprint 9: Integration & Hardening

**Goal:** Verify — not build — that what Sprints 2 through 8 produced actually satisfies the PRD, closes every open question left along the way, and holds up under a deliberate attempt to break it.

**Sprint outcome:** Every success metric in `PRD.md` §11 is checked and recorded (not assumed), every open question raised across Sprints 2–8 is either resolved-and-documented or explicitly deferred with a reason, a full permission-leak pass has been run across every endpoint and the WebSocket path, and a fresh clone of the repository can stand up the whole system and use it end to end.

## Epic: Cross-Cutting Open Question Audit

| ID    | Story                                           | Done when                                                                                                                                                                                                    |
| ----- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| S9-01 | Audit every open question raised in Sprints 2–8 | Walk through each one below and mark it resolved-and-implemented, resolved-but-not-yet-implemented (fix now), or explicitly deferred to Phase 2 with a one-line reason. No item is left in an unknown state. |

Carried-forward open questions to close out:

- Sprint 3: retry endpoint shape/limits; max file size and accepted MIME types.
- Sprint 4: top-k value; similarity threshold for `insufficient_evidence`; prompt template documented; LLM timeout/retry duration.
- Sprint 5: pagination style actually implemented consistently; max message length; single-instance WebSocket delivery limitation.
- Sprint 6: token storage strategy actually implemented as decided; UI error-display convention applied consistently.
- Sprint 7: last-owner-removal rule actually enforced; ingestion-status polling interval; invite-before-signup deferral confirmed as intentional.
- Sprint 8: WebSocket reconnect gap-fill behavior; bot loading-state timeout messaging.

Resolution record:

- **Sprint 4:** The canonical grounded prompt is documented in `docs/modules/bot.md`. LLM calls use a 30-second timeout and retry transient failures once after 1 second; both values are configurable.
- **Sprint 6:** The browser keeps access tokens in memory and refresh tokens in an HttpOnly cookie. UI errors use inline form/action messages for mutations and inline status blocks for loading failures.
- **Sprint 7:** Unknown invite emails intentionally return `404`; invite-before-signup is deferred to Phase 2.
- **Sprint 8:** Reconnect refetches and merges the newest message page. Bot requests show a "Still working" message after 3.5 seconds.

## Epic: Full Permission-Leak Pass

| ID    | Story                                                               | Done when                                                                                                                                                                                                                                                                                                                                                              |
| ----- | ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S9-02 | Manual black-box permission testing across every resource           | For every endpoint in `API.md` (workspaces, channels, memberships, files, messages, bot), manually attempt the request as: unauthenticated, authenticated-but-not-a-member, and authenticated-with-an-insufficient-role. Record actual results in a short test report — this is deliberately manual and adversarial, not just re-running the existing automated suite. |
| S9-03 | Consolidate per-sprint authorization matrices into one CI-run suite | S2-14, S3-11, S4-10, and S5-10's matrices run together in CI as one regression suite; confirms a later sprint's schema or endpoint change didn't silently break an earlier sprint's authorization guarantee.                                                                                                                                                           |
| S9-04 | Targeted leak testing on the two highest-risk paths                 | WebSocket connections and file downloads are the paths most likely to bypass standard request middleware. Specifically test: opening a WebSocket to a channel without membership; guessing/reusing a download URL for a file in a channel the caller isn't a member of.                                                                                                |

## Epic: Success Metrics Verification (PRD §11)

| ID    | Story                                           | Done when                                                                                                                                                                                                                            |
| ----- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| S9-05 | End-to-end workspace/channel/member walkthrough | A brand-new user signs up, creates a workspace and channel, invites a collaborator by email, and the collaborator gets real, correct access — done through the actual frontend, not direct API calls.                                |
| S9-06 | Final bot accuracy pass                         | Re-run Sprint 4's QA test set (S4-09) through the real frontend now that ingestion and UI both exist; record the final accuracy percentage against the PRD's 90% target; any miss is logged as a known issue, not silently dropped.  |
| S9-07 | Clean-checkout verification                     | Someone who has not set up this project before clones it fresh and follows `local-development.md` exactly, with no undocumented manual steps, and confirms `/health` returns `{"status":"ok"}` and the frontend loads and is usable. |
| S9-08 | Test coverage audit against PRD §6              | Confirm every MVP feature area (§6.1–§6.5) has both a success-path and a denial/error-path automated test somewhere in the suite; any gap found gets a test written now, not deferred.                                               |

## Epic: Reliability & Known-Limitations Documentation

| ID    | Story                                                           | Done when                                                                                                                                                                                                                                                   |
| ----- | --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S9-09 | Ingestion failure/retry verification under real conditions      | Deliberately upload a malformed/corrupt file and an oversized file; confirm each lands in a visible `failed` state with an actionable message (not silently lost), and that retry actually recovers a fixable case — per the PRD's reliability requirement. |
| S9-10 | Write a "Known Limitations" section                             | Documents deliberate v1 constraints as release notes rather than undiscovered gaps: single-instance WebSocket delivery, no invite-before-signup, and any Sprint 9 audit item explicitly deferred to Phase 2.                                                |
| S9-11 | Confirm `local-development.md` matches the actual current setup | If the project's database setup changed at any point during development (e.g. from local Docker Postgres to a hosted option), verify the documented steps still match reality exactly; fix any drift found.                                                 |

## Epic: Release Readiness

| ID    | Story                                                     | Done when                                                                                                                                                                                                                  |
| ----- | --------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| S9-12 | Confirm CI is green across backend and frontend on `main` | Both the backend (`ruff`/`pytest`) and frontend (lint/build) pipelines pass cleanly, including the consolidated S9-03 authorization suite.                                                                                 |
| S9-13 | Final PRD success-metrics sign-off                        | Walk through `PRD.md` §11 line by line with your collaborators and mark v1 explicitly done, or list precisely what's being deferred and why — a deliberate decision, not an implicit assumption that "it's probably fine." |

## Out of scope

- Any Phase 2 feature from `PRD.md` §7 (summarization, cross-channel search, more file types, notifications, integrations, analytics, production hosting/monitoring).
- New feature work of any kind — if something new is discovered as truly necessary during this sprint, it becomes a Phase 2 backlog item, not a Sprint 9 addition, to keep this sprint's purpose (verification) from quietly becoming more feature work.

## Definition of Done

- Findings from this sprint (leaks, gaps, drift) are fixed on a focused branch and reviewed through a pull request, same as any other sprint — hardening work isn't exempt from review.
- Every fix includes a regression test proving the specific issue found is actually closed.
- `ruff check`/`pytest` and frontend lint/build pass.
- Anything explicitly deferred is recorded, not just remembered.

## Sprint review checklist

- [x] Every open question carried in from Sprints 3–8 is resolved or explicitly deferred — none left ambiguous.
- [ ] The manual permission-leak pass (S9-02) found zero unresolved leaks, or every leak found has a merged fix and a regression test.
- [ ] The bot's final measured accuracy (S9-06) is recorded against the PRD's 90% target, whatever the result.
- [ ] A genuinely clean checkout works end to end, confirmed by someone other than whoever built the feature being tested.
- [ ] `PRD.md` §11's success metrics are each explicitly marked met, or the gap is documented as a known limitation.
- [ ] The "Known Limitations" doc (S9-10) exists and is accurate.
- [ ] With this sprint done, v1 is either genuinely release-ready, or you have a precise, honest list of what isn't — not a vague sense that it's "mostly there."
