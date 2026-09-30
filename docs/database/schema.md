# Initial Database Schema

PostgreSQL is the system of record. `pgvector` stores embeddings in the same database so retrieval can be filtered by channel in the database query.

## Entities

| Table            | Purpose                                                          |
| ---------------- | ---------------------------------------------------------------- |
| `users`          | Login identity and password hash.                                |
| `workspaces`     | Top-level team container.                                        |
| `channels`       | Isolated discussion and knowledge area belonging to a workspace. |
| `memberships`    | User-to-channel access and role.                                 |
| `files`          | File metadata and object-storage location.                       |
| `chunks`         | Parsed searchable content with citation metadata and embedding.  |
| `messages`       | Channel chat history.                                            |
| `refresh_tokens` | Rotated, revocable refresh-token records.                        |

## Required relationships

```text
users 1--many workspaces (owner_id)
workspaces 1--many channels
users many--many channels through memberships
channels 1--many files
files 1--many chunks
channels 1--many messages
users 1--many messages
users 1--many refresh_tokens
```

## Required constraints

- Every table uses a UUID primary key and UTC timestamps.
- `users.email` is unique and normalized to lowercase.
- `memberships` has a unique constraint on `(user_id, channel_id)`.
- `channels` has a unique constraint on `(workspace_id, name)`.
- `files.channel_id` is required.
- `chunks.file_id` is required; each chunk stores page or section metadata.
- `messages.channel_id` and `messages.user_id` are required.
- Roles use a controlled value set: `owner`, `admin`, `member`, `read_only`.
- Passwords and refresh tokens are never stored in plaintext.

## Important indexes

- `users(email)`
- `channels(workspace_id)`
- `memberships(user_id, channel_id)`
- `memberships(channel_id, role)`
- `files(channel_id)`
- `messages(channel_id, created_at)`
- Vector index on `chunks.embedding` after the embedding dimension is finalized.

## Deletion policy

- Deleting a workspace deletes its channels and memberships.
- Deleting a channel deletes memberships, messages, file metadata, and chunks.
- Deleting file metadata must also delete the corresponding object from MinIO.
- Deleting a user is restricted until ownership and membership relationships are reassigned or removed.
- Soft deletion should be considered for users, workspaces, and files once audit/history requirements are known.

## Finalized implementation decisions

- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`
- Embedding dimension: `384` (matches `chunks.embedding` and the question embedding contract)
- Alembic migrations live in `backend/migrations/`, with configuration in `backend/alembic.ini`.
- Whether messages and files use soft deletion
- Retention and backup policy
