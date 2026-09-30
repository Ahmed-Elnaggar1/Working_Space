# Branching Strategy

The default branch is `main`. Work is done on short-lived branches and merged through pull requests.

## Branch names

```text
feature/<short-description>
fix/<short-description>
docs/<short-description>
test/<short-description>
chore/<short-description>
```

Examples:

```text
feature/user-registration
fix/channel-membership-check
docs/sprint-1-contracts
```

## Workflow

1. Start from an updated `main`.
2. Create one focused branch for one story or small related change.
3. Make small commits that explain the change.
4. Run the checks locally.
5. Open a pull request with context, tests, and any database migration notes.
6. Review the diff and resolve comments.
7. Merge only when required checks pass.
8. Delete the branch after merging.

## Commit format

Use an imperative subject with a scope when useful:

```text
feat(auth): add password verification
fix(permissions): deny non-members
 docs: define Sprint 1 API contract
```

## Pull request checklist

- [ ] The PR is linked to a backlog story.
- [ ] Scope is focused and unrelated changes are excluded.
- [ ] Tests cover changed behavior, including denial cases where relevant.
- [ ] Documentation and API contracts are updated.
- [ ] Migrations are included and reversible where practical.
- [ ] No secrets, local databases, or generated files are committed.
