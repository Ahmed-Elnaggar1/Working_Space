# Repository Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── auth/          # Registration, login, tokens, password hashing
│   │   ├── bot/           # Retrieval and answer orchestration
│   │   ├── channels/      # Channel management and membership operations
│   │   ├── chat/          # Messages and WebSocket delivery
│   │   ├── files/         # File metadata, upload, download
│   │   ├── ingestion/     # Parsing, chunking, and embeddings
│   │   ├── permissions/   # Central authorization policy
│   │   ├── workspaces/    # Workspace management
│   │   └── main.py        # FastAPI application entry point
│   ├── tests/             # Backend unit and API tests
│   ├── Dockerfile         # Backend development image
│   └── requirements.txt   # Python dependencies
├── docs/
│   ├── api/               # API contracts
│   ├── architecture/     # Technical architecture and diagrams
│   ├── database/          # Schema and migration decisions
│   ├── development/       # Local workflow and repository conventions
│   ├── security/          # Threats and authorization rules
│   ├── sprints/           # Sprint goals, stories, and reviews
│   └── PRD.md             # Product requirements
├── frontend/              # Web client; currently reserved for implementation
├── docker-compose.yml     # Local backend, PostgreSQL, and MinIO stack
├── README.md              # Project entry point
└── .gitignore             # Local and generated files excluded from Git
```

## Ownership rules

- Routers translate HTTP/WebSocket requests and responses.
- Services contain business rules and coordinate repositories.
- Repositories contain persistence queries.
- `permissions` is the only module that owns authorization policy.
- Modules may call public functions from another module, but must not reach into its private implementation details.
- Database migrations are versioned and committed; generated data is never committed.
