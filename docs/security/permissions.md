# Permission Model

Authorization is enforced on the backend for every request. Frontend visibility is only a convenience and never a security boundary.

## Roles

| Action                 | Owner | Admin | Member | Read-only |
| ---------------------- | ----: | ----: | -----: | --------: |
| View channel           |   Yes |   Yes |    Yes |       Yes |
| View messages          |   Yes |   Yes |    Yes |       Yes |
| Send messages          |   Yes |   Yes |    Yes |        No |
| Ask the bot            |   Yes |   Yes |    Yes |       Yes |
| View files             |   Yes |   Yes |    Yes |       Yes |
| Upload files           |   Yes |   Yes |    Yes |        No |
| Delete own file        |   Yes |   Yes |    Yes |        No |
| Delete any file        |   Yes |   Yes |     No |        No |
| Add/remove members     |   Yes |   Yes |     No |        No |
| Change member roles    |   Yes |   Yes |     No |        No |
| Rename channel         |   Yes |   Yes |     No |        No |
| Delete channel         |   Yes |    No |     No |        No |
| Manage workspace owner |   Yes |    No |     No |        No |

## Enforcement algorithm

For every channel-scoped operation:

1. Authenticate the user.
2. Validate that the channel exists.
3. Load the user's membership for that channel.
4. Evaluate the requested action against the role.
5. Only then query or mutate channel data.
6. Return `403 Forbidden` when the user is authenticated but lacks permission.
7. Return `404 Not Found` when the resource should not be disclosed or does not exist.

The database query itself must include the channel scope. Never retrieve all chunks, files, or messages and filter them afterward.

## Rules

- A user must not access a channel solely because they know its ID.
- Membership checks apply to HTTP routes, WebSocket connections, downloads, search, and bot requests.
- A read-only member may retrieve permitted content but cannot mutate it.
- Role changes take effect on the next authorization check.
- The system must never include private resource names or content in denial responses.
- Authorization tests must cover every role and both allowed and denied outcomes.
