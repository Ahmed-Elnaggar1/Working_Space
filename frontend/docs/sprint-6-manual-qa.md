# Sprint 6 Frontend Manual QA

Run the backend and frontend locally before starting. Use a new browser session or private window for the signup flow.

## Smoke Flow (S6-20)

1. Open the frontend and visit `/signup`.
2. Register a new user with a valid email and a password of at least eight characters.
3. Confirm the app returns to `/login` with an account-created message.
4. Sign in with the new credentials.
5. Confirm the app navigates to `/workspaces`.
6. Create a workspace and confirm it appears without a full page refresh.
7. Open the workspace.
8. Create a channel and confirm it appears in the channel list without a full page refresh.
9. Open the channel and confirm the channel shell loads.
10. Refresh the browser on the channel or workspace URL and confirm the session is restored without returning to login.
11. Click `Sign out` and confirm the app returns to `/login`.
12. Visit `/workspaces` directly after logout and confirm it redirects to `/login`.

## Error-State Checks (S6-19)

| Status | How to trigger                                                                                                        | Expected UI                                                                        |
| ------ | --------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `401`  | Submit login with an incorrect password, or visit `/workspaces` after logout                                          | The login form shows the backend error, or the protected route redirects to login. |
| `403`  | Attempt to create a channel as a user who is not the workspace owner                                                  | The channel form shows the backend permission error.                               |
| `404`  | Visit `/workspaces/<unknown-id>` or `/channels/<unknown-id>` while authenticated                                      | The detail view shows the backend not-found error.                                 |
| `409`  | Register an existing email, create a duplicate workspace if rejected by the backend, or create a duplicate channel    | The relevant form shows the backend conflict message.                              |
| `422`  | Submit an empty or invalid form payload through the API contract, or use invalid input that passes browser validation | The relevant form shows the backend validation message.                            |

## Session Checks (S6-08, S6-11, S6-12)

- Refreshing an authenticated page uses the refresh-token cookie to restore the session.
- Logout revokes the server-side refresh session and clears the client authentication state.
- A previously revoked refresh token cannot restore the session.
