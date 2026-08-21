# Product Requirements Document (PRD)

**Product Name (working title):** Vault
**Owner:** Ahmed Elnaggar
**Status:** Draft v0.2
**Last updated:** 2026-08-20

---

## 1. Vision

A team workspace — similar in spirit to Discord — where each **channel** is an isolated space for a specific topic or project. Every channel holds its own files and materials, visible only to members with permission to that channel. A built-in **assistant bot** helps members search and retrieve information from the channel's materials, pointing to exactly where an answer came from (file + page/section), so people don't have to dig through documents manually.

This project is also being built as a learning exercise: to practice running a real product development lifecycle (docs → architecture → sprints → build → test → iterate), not just to write code.

## 2. Goals

- Give small teams a place to organize knowledge by topic, with real access control per channel.
- Let members find information fast via search, with traceable citations (file, page/section).
- Keep the system extensible so more capabilities (summarization, more integrations, etc.) can be added later without a rebuild.
- Use this build as a vehicle to practice professional SDLC process end-to-end.

## 3. Non-Goals (out of scope for v1)

- Voice/video chat.
- Real-time collaborative document editing.
- Mobile apps (web-first).
- Automatic summarization of files (planned for a later phase, not v1).
- Public/multi-tenant hosting for arbitrary strangers — v1 targets small, known teams (you + collaborators).

## 4. Users & Personas

| Persona                     | Description                                           | Needs                                                                 |
| --------------------------- | ----------------------------------------------------- | --------------------------------------------------------------------- |
| **Workspace Owner/Admin**   | Creates the workspace, manages channels & permissions | Full control, user management, channel creation                       |
| **Channel Member**          | Has access to specific channel(s)                     | Upload/view files, chat, ask the bot questions scoped to that channel |
| **Guest/Restricted Member** | Access to a limited subset of channels                | Same as member, but scoped visibility                                 |

## 5. Core Concepts

- **Workspace** — the top-level container (like a Discord server).
- **Channel** — an isolated space inside a workspace. Has its own members, files, and chat history. No cross-channel visibility unless explicitly granted.
- **Permission Roles** — per-channel roles: `owner`, `admin`, `member`, and `read_only`, enforced server-side rather than only represented in the UI.
- **Materials** — files/documents uploaded to a channel (PDFs, docs, etc.) that become searchable knowledge for that channel's bot.
- **Bot** — a per-channel assistant that answers questions using only that channel's materials, and cites its source (file name + page/section).

## 6. MVP Feature Scope (v1)

### 6.1 Workspace & Channels

- Create a workspace.
- Create/delete/rename channels within a workspace.
- Assign members to channels with a role (`admin`, `member`, or `read_only`); the workspace owner has full control.
- Channel isolation: a user only sees channels they're a member of.

### 6.2 Files & Materials

- Upload files to a channel (start with PDF + plain text; expand formats later).
- List/view/download files within a channel.
- Files are only accessible to that channel's members.

### 6.3 Chat

- Basic per-channel chat/message history (text only for v1).

### 6.4 Search Bot (v1 = search only, no summarization yet)

- Ask the bot a question inside a channel.
- Bot searches only that channel's ingested materials.
- Bot returns an answer **with citation**: file name + page number/section.
- No cross-channel search — respects the same isolation as the UI.

### 6.5 Auth & Permissions

- User accounts (email/password to start; SSO can come later).
- Per-channel role enforcement on every action (view, upload, ask bot).
- Short-lived access tokens and revocable, rotated refresh tokens.

## 7. Phase 2+ (explicitly deferred, for later roadmap)

- File summarization ("summarize this doc for me").
- Cross-file / cross-channel search (with permission awareness).
- More file types (docx, pptx, images with OCR).
- Notifications, mentions, threads.
- Integrations (Slack/Notion import, etc.).
- Usage analytics per channel.
- Advanced ingestion retry tooling and background worker infrastructure.
- Production hosting, backups, monitoring, and operational administration.

## 8. Key User Stories

1. As an **Admin**, I can create a channel and invite specific members so that only they can see its contents.
2. As a **Member**, I can upload a PDF to a channel so my team can reference it.
3. As a **Member**, I can ask the bot a question in a channel and get an answer that tells me which file and page it came from, so I can verify it myself.
4. As a **Member**, I cannot see or search materials in channels I'm not part of.
5. As an **Admin**, I can change a member's role in a channel (e.g., demote to read-only).

## 9. Functional Requirements

- FR1: System must enforce channel-level access control on every file, message, and bot query.
- FR2: Uploaded files must be parsed and chunked with page/section metadata preserved for citation.
- FR3: Bot responses must include a citation (file + location) for every factual claim drawn from a document.
- FR4: Search must be scoped to the requesting user's accessible channel(s) only — never leak across channels.
- FR5: Every channel-scoped operation must authenticate the user and authorize the requested action before reading or mutating channel data.
- FR6: File ingestion must expose a status such as `pending`, `processing`, `completed`, or `failed`.
- FR7: API errors must use a consistent documented structure and must not disclose private resource details.

## 10. Non-Functional Requirements

- **Security:** permission checks server-side, never trust client-side role checks alone.
- **Extensibility:** ingestion pipeline and permission model should be modular so Phase 2 features can be added without rearchitecting.
- **Data isolation:** channel data (files + embeddings) must be logically separated, even if stored in shared infrastructure.
- **Reliability:** failed ingestion must be visible and retryable without silently losing the uploaded file.
- **Operability:** local development must be reproducible with Docker Compose and provide health and API documentation endpoints.

## 11. Success Metrics (v1)

- Can create a workspace, channel, and invite a collaborator end-to-end.
- Bot correctly answers a test question with an accurate file/page citation for at least a defined test set of documents (e.g., 90%+ accuracy on a manual QA set).
- No permission leaks in manual isolation testing (a non-member cannot access a channel's files/search via API or UI).
- A clean checkout can start the local stack and verify `GET /health` returns `{"status":"ok"}`.
- Every MVP feature has automated tests for its primary success case and relevant denial/error cases.

## 12. V1 Technical Direction

Since search/citation is the core hard problem, this is really a **RAG (Retrieval-Augmented Generation)** system wrapped in a permissioned chat app. Suggested starting stack:

| Layer         | Decision                                            | Notes                                                                                       |
| ------------- | --------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| Frontend      | React + Next.js                                     | SPA-style workspace/channel UI                                                              |
| Backend/API   | Python + FastAPI                                    | Keeps API and RAG/ingestion work in one language                                            |
| Auth          | Email/password with JWT access and refresh tokens   | Access tokens are short-lived; refresh tokens are rotated and revocable; OAuth/SSO deferred |
| Primary DB    | PostgreSQL                                          | Users, workspaces, channels, memberships, roles, messages, and file metadata                |
| Vector store  | pgvector inside PostgreSQL                          | Retrieval stays in the same database and can be filtered by channel                         |
| File storage  | MinIO locally; S3-compatible storage in production  | File bytes are not stored in PostgreSQL                                                     |
| Realtime chat | FastAPI WebSockets                                  | Connections are authenticated and channel-scoped                                            |
| LLM           | Claude API                                          | External production dependency for grounded bot answers                                     |
| Ingestion     | Python parser/chunker with page or section metadata | Start with PDF and plain text; exact parser packages are implementation decisions           |

These choices are the v1 direction. The embedding model, vector dimension, exact parser packages, and production hosting remain implementation decisions.

## 14. Next Steps

1. Review and edit this PRD with your collaborators — treat it as a living doc.
1. Keep the [Technical Architecture Doc](architecture/Architecture.md), [API contract](api/API.md), [database schema](database/schema.md), and [permission model](security/permissions.md) synchronized with approved decisions.
1. Break the MVP into epics and sprint-sized tickets in the [Sprint 1 backlog](sprints/sprint-1.md).
1. Implement the first vertical slice: signup, login, workspace, channel, membership, and permission enforcement.
1. Set up a lightweight project board and use the Definition of Done for every story.
