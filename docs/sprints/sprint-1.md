# Sprint 1: Foundations

**Goal:** Make the project reproducible and turn the product design into implementable contracts.

**Sprint outcome:** A new contributor can understand the repository, start the local stack, review the schema and permissions, and use the API draft to begin implementation.

## Stories

| ID    | Story                         | Done when                                                                                             |
| ----- | ----------------------------- | ----------------------------------------------------------------------------------------------------- |
| S1-01 | Document repository structure | `docs/development/repository-structure.md` exists and matches the repository.                         |
| S1-02 | Define branching workflow     | `docs/development/branching.md` defines branch names, pull requests, and merge rules.                 |
| S1-03 | Document local development    | `docs/development/local-development.md` explains prerequisites, startup, health checks, and shutdown. |
| S1-04 | Define database schema        | `docs/database/schema.md` defines entities, keys, relationships, indexes, and deletion behavior.      |
| S1-05 | Define permission model       | `docs/security/permissions.md` defines roles, actions, enforcement rules, and denial behavior.        |
| S1-06 | Draft API contract            | `docs/api/API.md` defines initial endpoints, request/response shapes, auth, and errors.               |
| S1-07 | Verify the foundation         | Documentation links work, the health endpoint has an automated test, and local setup is recorded.     |

## Out of scope

- Full authentication implementation
- Frontend implementation
- File ingestion and embeddings
- LLM integration
- Production deployment

## Definition of Done

- The change is on a focused branch and reviewed through a pull request.
- Documentation and API behavior agree.
- Automated tests cover new executable behavior.
- Security-sensitive behavior has a negative test, not only a happy-path test.
- `ruff check` and `pytest` pass.
- Any unresolved decision is recorded as an open question or ADR.

## Sprint review checklist

- [ ] A clean checkout can follow the local setup guide.
- [ ] `/health` returns `{"status":"ok"}`.
- [ ] Schema supports channel isolation through memberships.
- [ ] Every channel-scoped endpoint requires an authorization decision.
- [ ] API errors use one documented shape.
- [ ] Next sprint backlog is created from the remaining gaps.
