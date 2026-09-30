# Vault

Vault is a permissioned team workspace where channels isolate conversations,
files, and searchable knowledge. The project is also a learning exercise for
professional product and software development practices.

## Current status

Sprint 1 is focused on foundations and contracts. The backend currently exposes
a health endpoint while the product, architecture, schema, permission model,
API contract, and development workflow are being defined.

## Start locally

Prerequisite: Docker Desktop must be running with its Linux engine enabled.

```powershell
docker compose up --build
```

Verify the backend at:

- `http://localhost:8000/health`
- `http://localhost:8000/docs`

The complete local workflow is documented in
[docs/development/local-development.md](docs/development/local-development.md).

## Documentation

- [Product requirements](docs/PRD.md)
- [Technical architecture](docs/architecture/Architecture.md)
- [Sprint 1 backlog](docs/sprints/sprint-1.md)
- [Repository structure](docs/development/repository-structure.md)
- [Branching strategy](docs/development/branching.md)
- [Local development](docs/development/local-development.md)
- [Database schema](docs/database/schema.md)
- [Permission model](docs/security/permissions.md)
- [API contract draft](docs/api/API.md)

## Development checks

Inside the backend container:

```powershell
docker compose exec backend pytest
docker compose exec backend ruff check .
```

Do not commit `.env` files, secrets, database volumes, or generated files.
