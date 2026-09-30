# Workspaces Module

## 1. High-Level Overview & Architecture

The **Workspaces Module** (`backend/app/workspaces/`) manages the top-level organizational containers (tenants) of the platform. Workspaces serve as the root boundary for grouping channels, documents, messages, and collaborative teams.

Key architectural capabilities include:
1. **Atomic Provisioning with Default Assets**: When a workspace is created, the system atomically provisions a default `"general"` channel and enrolls the creator as the channel's `owner` in a single database transaction.
2. **Access-Controlled Discovery via SQL Subqueries**: Users can query all workspaces they are authorized to access. A user has access to a workspace if they are either the **workspace owner** OR a **member of at least one channel** within that workspace.
3. **Cascade Containment**: Deleting a workspace cascades through all associated child entities (`channels`, `files`, `chunks`, `messages`, and `memberships`), preventing data leaks or orphaned records.

```mermaid
flowchart TD
    subgraph Client ["Client / Authenticated User"]
        A[POST /workspaces/ <br> {name: "Engineering"}]
        B[GET /workspaces/ <br> (List Accessible Workspaces)]
    end

    subgraph Workspace Routes ["app/workspaces/routes.py"]
        C["create_workspace <br> (Injects CurrentUser & AsyncSession)"]
        D["list_workspaces <br> (Injects CurrentUser & AsyncSession)"]
        A --> C
        B --> D
    end

    subgraph Workspace Service ["app/workspaces/service.py"]
        E["create_workspace_with_defaults"]
        F["get_user_workspaces"]
        C --> E
        D --> F
    end

    subgraph Atomic Creation Transaction ["Single Commit"]
        E --> G["1. Insert Workspace (owner_id = user.id)"]
        G --> H["2. Insert Default Channel ('general')"]
        H --> I["3. Insert Membership (role = 'owner')"]
    end

    subgraph Query Optimization ["EXISTS Subquery"]
        F --> J["SELECT Workspace WHERE <br> owner_id == user.id OR EXISTS(Channel Membership)"]
    end

    I --> K[PostgreSQL Database]
    J --> K
```

---

## 2. Step-by-Step Code Walkthrough & File Map

To trace how workspaces are created and listed, follow these step-by-step file interactions:

### Step 1: Workspace Creation Ingress
📂 **[app/workspaces/routes.py](../../backend/app/workspaces/routes.py)**
- **Endpoint**: `POST /workspaces/`
- **Authentication**: Requires valid bearer token via `CurrentUser = Depends(get_current_user)`.
- **Validation**: [schemas.py](../../backend/app/workspaces/schemas.py) verifies `WorkspaceCreate` (`name` minimum 1, maximum 255 characters).
- **Delegation**: Calls `service.create_workspace_with_defaults(db, payload=payload, owner_id=current_user.id)`.

---

### Step 2: Atomic Workspace & Default Channel Provisioning
📂 **[app/workspaces/service.py](../../backend/app/workspaces/service.py)**
- **`create_workspace_with_defaults(db, payload, owner_id)`**:
  - Rather than executing disjointed database writes, uses SQLAlchemy's declarative relationship nesting:
    ```python
    workspace = Workspace(
        name=payload.name,
        owner_id=owner_id,
        channels=[
            Channel(
                name="general",
                memberships=[
                    Membership(user_id=owner_id, role=Role.OWNER),
                ],
            )
        ],
    )
    db.add(workspace)
    await db.commit()
    ```
  - **Atomicity Guarantee**: The `workspaces`, `channels`, and `memberships` tables are populated in a single atomic SQL transaction. It is impossible to encounter a state where a workspace exists without its `"general"` channel or without its owner enrolled.
  - Returns the newly refreshed `Workspace` model serialized into [WorkspaceResponse](../../backend/app/workspaces/schemas.py).

---

### Step 3: Accessible Workspaces Listing
📂 **[app/workspaces/routes.py](../../backend/app/workspaces/routes.py)** & **[app/workspaces/service.py](../../backend/app/workspaces/service.py)**
- **Endpoint**: `GET /workspaces/`
- **Access Rule**: A user can see a workspace if:
  1. They are the workspace owner (`Workspace.owner_id == user_id`), **OR**
  2. They belong to at least one channel in that workspace (`EXISTS (SELECT 1 FROM memberships ...)`).
- **Optimized SQL Query**:
  ```python
  has_channel_membership = exists(
      select(Membership.id)
      .join(Channel, Channel.id == Membership.channel_id)
      .where(
          Channel.workspace_id == Workspace.id,
          Membership.user_id == user_id,
      )
  )

  stmt = (
      select(Workspace)
      .where(or_(Workspace.owner_id == user_id, has_channel_membership))
      .order_by(Workspace.created_at.desc())
  )
  ```
  - Using an `EXISTS` semi-join subquery guarantees high query performance and avoids duplicate rows caused by joining across multiple channel memberships.

---

## 3. Module Components Summary

| File | Primary Responsibility | Key Functions / Classes |
| :--- | :--- | :--- |
| **[app/workspaces/routes.py](../../backend/app/workspaces/routes.py)** | REST API endpoints for workspace creation and listing | `create_workspace`, `list_workspaces` |
| **[app/workspaces/service.py](../../backend/app/workspaces/service.py)** | Core business logic: atomic provisioning and `EXISTS` membership filtering | `create_workspace_with_defaults`, `get_user_workspaces` |
| **[app/workspaces/schemas.py](../../backend/app/workspaces/schemas.py)** | Pydantic validation and response serialization schemas | `WorkspaceCreate`, `WorkspaceResponse`, `ChannelSummaryResponse` |

---

## 4. Integration with Other Modules

| Module | Interaction with Workspaces | Key Files |
| :--- | :--- | :--- |
| **Auth Module** | • Authenticates workspace operations and injects `current_user.id`. | [app/auth/dependencies.py](../../backend/app/auth/dependencies.py) |
| **Channels Module** | • Channels are nested under workspaces via `workspace_id`.<br>• Creating new channels (`POST /workspaces/{id}/channels`) checks `workspace.owner_id`. | [app/channels/routes.py](../../backend/app/channels/routes.py) |
| **Models & Database** | • `Workspace` relationship with `Channel` specifies `cascade="all, delete-orphan"`. | [app/models.py](../../backend/app/models.py) |

---

## 5. Technical Considerations

### 1. Atomic Multi-Table Provisioning
- **Design**: Leveraging SQLAlchemy ORM cascaded additions (`channels=[Channel(..., memberships=[...])]`) ensures that all foreign keys are populated in the correct sequence by the unit of work, eliminating partial-state bugs if an error occurs during workspace initialization.

### 2. Scalable Membership Discovery via `EXISTS` Subquery
- **Design**: If a user is a member of 50 channels inside a single workspace, a naive `JOIN` query would produce 50 redundant rows per workspace requiring in-memory `DISTINCT` deduplication. Using `EXISTS(...)` lets the PostgreSQL query planner terminate the search as soon as the first matching channel membership is found.
