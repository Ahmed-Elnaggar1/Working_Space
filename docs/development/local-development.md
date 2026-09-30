# Local Development

## Prerequisites

- Git
- Docker Desktop with the Linux engine running
- A code editor
- Optional: Python 3.12 for running backend commands outside Docker

## Start the stack

From the repository root:

```powershell
docker compose up --build
```

Run detached when you want the terminal back:

```powershell
docker compose up --build -d
```

## Verify services

```powershell
docker compose ps
```

Open these URLs:

- `http://localhost:8000/health` should return `{"status":"ok"}`.
- `http://localhost:8000/docs` opens FastAPI's interactive API documentation.
- `http://localhost:9001` opens the MinIO console.

The root URL `http://localhost:8000` is not an application page yet and may return `404`.

## Stop the stack

```powershell
docker compose down
```

This stops containers while preserving named volumes. To remove local database and object-storage data too:

```powershell
docker compose down -v
```

Use `-v` only when intentionally resetting local data.

## Troubleshooting

If Docker reports that `dockerDesktopLinuxEngine` cannot be found, start Docker Desktop and wait until it reports that the engine is running.

If port `8000`, `5432`, `9000`, or `9001` is already in use, stop the conflicting process or change the host-side port before starting Compose.

## Development checks

Once the test suite exists, run:

```powershell
docker compose exec backend pytest
docker compose exec backend ruff check .
```

The current application has a health endpoint; feature-specific checks will be added with each module.
