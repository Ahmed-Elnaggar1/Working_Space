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

Accepts a refresh token via `HttpOnly` cookie or JSON payload `{"refresh_token":"jwt"}` and returns a rotated access token and refresh token. Refresh tokens must be revocable and must not be stored plaintext.

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

### `GET /channels/{channel_id}/files`

Returns files visible to the caller in that channel.

### `GET /channels/{channel_id}/files/{file_id}/download`

Streams a file only after verifying both the file's channel and the caller's membership.

### `POST /channels/{channel_id}/files/{file_id}/retry-ingestion`

Retries the ingestion process for a failed file. Requires upload files permission. Returns the updated file metadata with the ingestion status set back to `pending`.

## Chat

### `GET /channels/{channel_id}/messages`

Returns paginated messages ordered by `created_at` ascending. Pagination uses
`limit` (1-100, default 50) and `offset` (default 0) query parameters. Message
content is required and limited to 4000 characters.

### `POST /channels/{channel_id}/messages`

Request: `{"content":"Message text"}`

Requires send-message permission.

### `WS /ws/channels/{channel_id}`

Requires authentication and channel membership during connection establishment.
Clients authenticate with `?token=<access_token>` (an `Authorization: Bearer`
header is also accepted). Each received JSON message has the shape
`{"content":"Message text"}`. Every message is validated against the sender's
current membership and role; a role change takes effect on the next message,
and membership removal closes the connection with WebSocket close code 1008.
Persisted messages are broadcast to other clients in the same channel only.
The connection manager is in-memory and therefore intended for the current
single-backend deployment; multi-instance delivery requires shared messaging.

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
