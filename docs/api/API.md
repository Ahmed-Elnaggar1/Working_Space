# API Contract Draft

This is the initial REST contract. The implementation may refine field names, but changes must be reviewed against this document.

## Conventions

- Base URL: `http://localhost:8000`
- JSON request and response bodies unless stated otherwise
- Protected endpoints use `Authorization: Bearer <access_token>`
- IDs are UUID strings
- Timestamps are ISO 8601 UTC strings

## Error shape

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "You do not have permission to perform this action.",
    "request_id": "uuid"
  }
}
```

Do not include private resource details in authorization errors.

## Health

### `GET /health`

Response `200`:

```json
{ "status": "ok" }
```

## Authentication

### `POST /auth/signup`

Request:

```json
{ "email": "person@example.com", "password": "strong-password" }
```

Response `201`:

```json
{ "user": { "id": "uuid", "email": "person@example.com" } }
```

### `POST /auth/login`

Request:

```json
{ "email": "person@example.com", "password": "strong-password" }
```

Response `200`:

```json
{ "access_token": "jwt", "refresh_token": "jwt", "token_type": "bearer" }
```

### `POST /auth/refresh`

The browser uses the rotated refresh token from the `HttpOnly` cookie and receives an access token in the response. Refresh tokens are also accepted in the JSON payload for non-browser clients. Refresh tokens must be revocable and must not be stored plaintext.

### `POST /auth/logout`

Request: optional `{"refresh_token":"jwt"}` (or via `refresh_token` cookie).

Revokes the caller's refresh token server-side (`revoked_at` set in database) and clears the cookie. Returns `204 No Content`. Subsequent attempts to use this token at `/auth/refresh` will be rejected.

## Workspaces and channels

### `POST /workspaces`

Request: `{"name":"Engineering"}`

Response `201`: workspace object with `id`, `name`, `owner_id`, and `created_at`.

### `GET /workspaces`

Returns a list of workspace objects the caller owns or has at least one channel membership in. Unrelated users receive an empty list `[]`.

Response `200`: `[ { "id": "uuid", "name": "Engineering", "owner_id": "uuid", "created_at": "timestamp" } ]`

### `GET /workspaces/{workspace_id}`

Returns the workspace object if the caller is the owner or a member of at least one channel in the workspace. If the workspace does not exist or the caller is not authorized, returns `404 Not Found` (anti-reconnaissance rule matching S2-07).

Response `200`: `{ "id": "uuid", "name": "Engineering", "owner_id": "uuid", "created_at": "timestamp" }`

### `POST /workspaces/{workspace_id}/channels`

Request: `{"name":"Backend"}`

Response `201`: channel object with `id`, `workspace_id`, `name`, and `created_at`.

### `GET /workspaces/{workspace_id}/channels`

Lists only the channels within that workspace the caller is a member of (per the channel isolation rule in permissions). Returns `404 Not Found` if the workspace does not exist or the caller has no access to the workspace.

Response `200`: `[ { "id": "uuid", "workspace_id": "uuid", "name": "general", "created_at": "timestamp" } ]`

### `GET /channels/{channel_id}`

Returns a channel only when the caller has membership.

## Memberships

### `GET /channels/{channel_id}/members`

Returns the channel's members, each with their `id`, `user_id`, `email`, `channel_id`, and `role`. Any channel member can view this list, including `read_only` members.

Response `200`:

```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "email": "member@example.com",
    "channel_id": "uuid",
    "role": "owner"
  }
]
```

### `POST /channels/{channel_id}/members`

Request:

```json
{ "email": "member@example.com", "role": "member" }
```

The server resolves the email to the matching user account. The endpoint also accepts the legacy `user_id` form for compatibility, but the canonical contract is email-based. Requires `owner` or `admin`.

Returns `404 Not Found` if no account exists for that email, and `409 Conflict` if the user is already a member of the channel.

### `PATCH /channels/{channel_id}/members/{user_id}`

Request: `{"role":"read_only"}`

Requires `owner` or `admin`.

### `DELETE /channels/{channel_id}/members/{user_id}`

Removes membership. Requires `owner` or `admin`.

## Files

### `POST /channels/{channel_id}/files`

Multipart upload. Requires upload permission. The response includes file metadata and an ingestion status, never raw file content.
Uploads are limited to 10 MiB by default. Accepted files must use the `.pdf` extension with `application/pdf` or the `.txt` extension with `text/plain`; the extension and declared MIME type must agree. The size limit is configurable with `MAX_FILE_SIZE_BYTES`.

### `GET /channels/{channel_id}/files`

Returns files visible to the caller in that channel.

### `GET /channels/{channel_id}/files/{file_id}/download`

Streams a file only after verifying both the file's channel and the caller's membership.

### `POST /channels/{channel_id}/files/{file_id}/retry-ingestion`

Retries the ingestion process for a failed file. Requires upload files permission. Returns the updated file metadata with the ingestion status set back to `pending`.
The initial ingestion is followed by at most 3 retries by default. Each retry increments `ingestion_retry_count`; once the limit is reached, the endpoint returns `429 Too Many Requests`. The limit is configurable with `MAX_INGESTION_RETRIES`.

## Bot reliability and prompt contract

The bot uses the canonical grounded prompt documented in `docs/modules/bot.md`. Provider calls have a 30-second timeout by default and retry once after a 1-second delay for timeouts, connection failures, HTTP 429, and HTTP 5xx responses. These values are configurable with `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, and `LLM_RETRY_DELAY_SECONDS`.

## Chat

### `GET /channels/{channel_id}/messages`

Returns a page of messages ordered by `created_at` ascending. Pagination uses
`limit` (1-100, default 50) and an optional opaque `before` cursor. The initial
request returns the newest page; pass the response's `next_cursor` as `before`
to load older messages without offset drift while new messages arrive.

Response:

```json
{
  "items": [
    { "id": "uuid", "content": "Message text", "created_at": "timestamp" }
  ],
  "next_cursor": "opaque-cursor-or-null"
}
```

Message content is required and limited to 4000 characters.

### `POST /channels/{channel_id}/messages`

Request:
```json
{
  "content": "Message text",
  "parent_message_id": "uuid-optional"
}
```

Requires send-message permission. If `parent_message_id` is supplied, it must identify a message within the same channel whose own `parent_message_id` is null (nested thread replies are rejected with `400`).

### `GET /channels/{channel_id}/messages/{message_id}/thread`

Returns the replies belonging to a message thread, ordered chronologically by `created_at`.
Requires view-messages permission.

Response `200`:
```json
{
  "parent": {
    "id": "uuid",
    "channel_id": "uuid",
    "user_id": "uuid",
    "content": "Root message text",
    "created_at": "timestamp"
  },
  "items": [
    {
      "id": "uuid",
      "channel_id": "uuid",
      "user_id": "uuid",
      "parent_message_id": "uuid",
      "content": "Reply text",
      "created_at": "timestamp"
    }
  ]
}
```

### `WS /ws/channels/{channel_id}`

Requires authentication and channel membership during connection establishment.
Clients authenticate with `?token=<access_token>` (an `Authorization: Bearer`
header is also accepted). The token is decoded and its expiry is checked during
the handshake; missing, invalid, or expired credentials are rejected with
WebSocket close code `1008`. Each received JSON message has the shape
`{"content":"Message text"}` or `{"content":"Message text", "parent_message_id":"uuid"}`.
Every message is validated against the sender's current membership and role;
a role change takes effect on the next message, and membership removal closes
the connection with WebSocket close code 1008. Persisted messages are broadcast
to other clients in the same channel only. The connection manager is in-memory
and therefore intended for the current single-backend deployment; multi-instance
delivery requires shared messaging.

## Notifications

### `GET /notifications`

Paginated, newest-first notifications inbox scoped strictly to the authenticated caller.
Query params: `limit` (default 50, 1-100), `before` (cursor).

Response `200`:
```json
{
  "items": [
    {
      "id": "uuid",
      "user_id": "uuid",
      "actor_id": "uuid",
      "channel_id": "uuid",
      "message_id": "uuid",
      "type": "mention",
      "is_read": false,
      "created_at": "timestamp"
    }
  ],
  "next_cursor": "opaque-cursor-or-null"
}
```

### `GET /notifications/unread-count`

Computes the caller's live unread notifications count.

Response `200`:
```json
{
  "unread_count": 3
}
```

### `PATCH /notifications/{id}/read`

Marks a single notification belonging to the caller as read.
Attempting to mark another user's notification returns `404` or `403`.

Response `200`:
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "actor_id": "uuid",
  "channel_id": "uuid",
  "message_id": "uuid",
  "type": "mention",
  "is_read": true,
  "created_at": "timestamp"
}
```

### `PATCH /notifications/read-all`

Marks all unread notifications belonging to the caller as read.

Response `200`:
```json
{
  "marked_read_count": 3
}
```

### `WS /ws/notifications`

Per-user real-time notification WebSocket.
Authenticated via query param `?token=<access_token>` or `Authorization: Bearer <access_token>`.
Rejects invalid/missing tokens with code `1008`.
Pushes new notification objects to the connected user in real time upon mention or thread reply.


## Bot

### `POST /channels/{channel_id}/ask`

Request:

```json
{ "question": "What is the release date?" }
```

Response:

```json
{
  "answer": "The release date is ...",
  "citations": [{ "file_id": "uuid", "file_name": "plan.pdf", "page": 4 }],
  "insufficient_evidence": false
}
```

Retrieval must filter by `channel_id` in the database query before results are sent to the LLM.

## Standard status codes

- `200` success
- `201` resource created
- `204` successful deletion with no response body
- `400` malformed request
- `401` missing or invalid authentication
- `403` authenticated but not authorized
- `404` resource not found or intentionally undisclosed
- `409` duplicate or conflicting resource
- `422` validation failure
- `500` unexpected server error
