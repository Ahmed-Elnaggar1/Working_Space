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
{ "access_token": "jwt", "token_type": "bearer" }
```

### `POST /auth/refresh`

Accepts a refresh token and returns a rotated access token. Refresh tokens must be revocable and must not be stored plaintext.

## Workspaces and channels

### `POST /workspaces`

Request: `{"name":"Engineering"}`

Response `201`: workspace object with `id`, `name`, `owner_id`, and `created_at`.

### `POST /workspaces/{workspace_id}/channels`

Request: `{"name":"Backend"}`

Response `201`: channel object with `id`, `workspace_id`, `name`, and `created_at`.

### `GET /channels/{channel_id}`

Returns a channel only when the caller has membership.

## Memberships

### `POST /channels/{channel_id}/members`

Request:

```json
{ "user_id": "uuid", "role": "member" }
```

Requires `owner` or `admin`.

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

## Chat

### `GET /channels/{channel_id}/messages`

Returns paginated messages ordered by `created_at`.

### `POST /channels/{channel_id}/messages`

Request: `{"content":"Message text"}`

Requires send-message permission.

### `WS /ws/channels/{channel_id}`

Requires authentication and channel membership during connection establishment. Every received message is validated against the sender's role.

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
