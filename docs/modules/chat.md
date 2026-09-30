# Chat Module

## 1. High-Level Overview & Architecture

The **Chat Module** (`backend/app/chat/`) provides both real-time full-duplex communication and persistent message storage for channels. It combines RESTful endpoints for message history with WebSockets for instantaneous real-time broadcasting across connected clients.

Key architectural capabilities include:
1. **Full-Duplex WebSockets**: Real-time communication via `/ws/channels/{channel_id}` supporting multi-client messaging within channel scopes.
2. **Dynamic Mid-Session Authorization**: Unlike static auth checks that only run at connection time, the WebSocket event loop re-evaluates the user's role on **every message frame** (`populate_existing=True`). If a user is demoted or removed while connected, their write privileges are revoked immediately.
3. **Thread-Safe In-Memory Connection Pooling**: The [ChannelConnectionManager](../../backend/app/chat/manager.py) manages WebSocket connection pools per channel with `asyncio.Lock()` to ensure race-free additions, broadcasts, and disconnects.
4. **Dead Socket Pruning**: Automatically detects closed or broken client connections during broadcast cycles and purges them from memory without disrupting other channel participants.
5. **Indexed History Retrieval**: Messages are indexed by `(channel_id, created_at)` for high-performance paginated queries (`GET /channels/{channel_id}/messages`).

```mermaid
flowchart TD
    subgraph Client ["Client / WebSocket"]
        A[WS Handshake: /ws/channels/{id}?token=...]
        B[Send JSON Message Frame]
        C[REST: GET /messages?limit=50]
    end

    subgraph Chat Routes ["app/chat/routes.py"]
        D["WS Handshake: authenticate_access_token"]
        E["Verify Channel Membership"]
        F["Receive Message Frame"]
        G["GET /channels/{id}/messages <br> [require_role: view_messages]"]
    end

    subgraph Auth & Permissions ["app/permissions/"]
        E --> H{"Active Member?"}
        H -- No --> I["Close WS (code 1008)"]
        H -- Yes --> J["Accept Connection"]
        F --> K["Re-check Role: 'send_messages' <br> (populate_existing=True)"]
        K -- Denied --> L["Send Error JSON & Continue"]
    end

    subgraph Connection Manager ["app/chat/manager.py"]
        J --> M["connection_manager.connect(channel_id, ws)"]
        K -- Allowed --> N["Persist to Database"]
        N --> O["connection_manager.broadcast(channel_id, payload)"]
        O --> P["Emit to Channel Sockets <br> (skip sender)"]
    end

    subgraph Persistence Layer ["app/models.py"]
        N --> Q["messages table <br> (channel_id, user_id, content)"]
        G --> Q
    end

    A --> D --> E
    B --> F
    C --> G
```

---

## 2. Step-by-Step Code Walkthrough & File Map

To trace how chat messages are sent, broadcast, and retrieved, follow these step-by-step file interactions:

### Step 1: WebSocket Handshake & Authentication
📂 **[app/chat/routes.py](../../backend/app/chat/routes.py)**
- **Endpoint**: `WebSocket /ws/channels/{channel_id}`
- **Authentication Handshake**:
  1. Extracts token from either query parameters (`?token=<jwt>`) or the `Authorization: Bearer <jwt>` header (accommodating browser environments where WebSocket APIs cannot pass custom headers).
  2. Authenticates the token using `authenticate_access_token(token)`. If missing or invalid, closes connection immediately with close code `1008` (Policy Violation).
  3. Queries `Channel` and `Membership` tables. If the channel does not exist or the user is not a member, closes with code `1008`.
  4. Accepts WebSocket connection: `await websocket.accept()`.
  5. Registers socket in pool: `await connection_manager.connect(channel_id, websocket)`.

---

### Step 2: Real-Time Event Loop & Dynamic Role Verification
📂 **[app/chat/routes.py](../../backend/app/chat/routes.py)**
- **WebSocket Receiving Loop**:
  1. Receives message payload: `data = await websocket.receive_json()`.
  2. **Dynamic Role Check**:
     ```python
     membership = await db.scalar(
         select(Membership).where(...)
         .execution_options(populate_existing=True)
     )
     ```
     *Security Feature*: `populate_existing=True` forces SQLAlchemy to refresh the membership from the database, preventing stale cached session roles.
  3. If membership has been deleted, sends error and closes connection (`1008`).
  4. Evaluates role against `ROLE_PERMISSIONS`:
     - If `"send_messages"` is not permitted for the user's role (e.g. `Role.READ_ONLY`), sends `{"error": "Permission denied"}` back to the socket and does not broadcast.
  5. Validates payload structure against [MessageCreate](../../backend/app/chat/schemas.py) (`content` min length 1, max length 4000).

---

### Step 3: Message Persistence
📂 **[app/chat/service.py](../../backend/app/chat/service.py)**
- **`persist_message(db, channel_id, user_id, payload)`**:
  - Inserts a new `Message` record with `channel_id`, `user_id`, and `content`.
  - Commits transaction and refreshes model attributes (`id`, `created_at`).
  - Returns the persisted `Message` instance.

---

### Step 4: Broadcasting & Dead Connection Cleanup
📂 **[app/chat/manager.py](../../backend/app/chat/manager.py)**
- **`connection_manager.broadcast(channel_id, payload, sender=websocket)`**:
  1. Acquires `asyncio.Lock()` to create an immutable snapshot of active connections for the channel.
  2. Iterates over all connected sockets in that channel, skipping the original `sender`.
  3. Sends serialized JSON (`await websocket.send_json(payload)`).
  4. If a socket send fails (e.g. client crashed or closed browser tab unexpectedly), records the broken socket in `failed_connections`.
  5. Unregisters all failed sockets from the pool cleanly, preventing memory leaks and stale connection accumulation.

---

### Step 5: REST Endpoints (Creation & History Pagination)
📂 **[app/chat/routes.py](../../backend/app/chat/routes.py)**
- **`create_message` (`POST /channels/{channel_id}/messages`)**:
  - REST alternative to WebSocket message sending.
  - Guarded by `@require_role("send_messages")`.
  - Persists message and returns `HTTP 201 Created` with [MessageResponse](../../backend/app/chat/schemas.py).
- **`get_messages` (`GET /channels/{channel_id}/messages`)**:
  - Guarded by `@require_role("view_messages")` (all members including `read_only`).
  - Supports pagination parameters: `limit` (default 50, range 1–100) and `offset` (default 0).
  - Returns chronologically ordered messages (`order_by(Message.created_at.asc(), Message.id.asc())`).

---

## 3. Module Components Summary

| File | Primary Responsibility | Key Functions / Classes |
| :--- | :--- | :--- |
| **[app/chat/routes.py](../../backend/app/chat/routes.py)** | WebSocket endpoint and REST message history routes | `channel_websocket`, `create_message`, `get_messages` |
| **[app/chat/manager.py](../../backend/app/chat/manager.py)** | In-memory thread-safe WebSocket connection registry | `ChannelConnectionManager`, `connect`, `disconnect`, `broadcast` |
| **[app/chat/service.py](../../backend/app/chat/service.py)** | Database persistence logic for messages | `persist_message` |
| **[app/chat/schemas.py](../../backend/app/chat/schemas.py)** | Pydantic request and response schemas | `MessageCreate`, `MessageResponse` |

---

## 4. Integration with Other Modules

| Module | Interaction with Chat | Key Files |
| :--- | :--- | :--- |
| **Auth Module** | • Authenticates WebSocket tokens via `authenticate_access_token`.<br>• REST endpoints use `get_current_user` dependency. | [app/auth/dependencies.py](../../backend/app/auth/dependencies.py) |
| **Permissions Module** | • REST endpoints use `@require_role("send_messages")` and `@require_role("view_messages")`.<br>• WebSocket loop validates actions against `ROLE_PERMISSIONS`. | [app/permissions/dependencies.py](../../backend/app/permissions/dependencies.py) |
| **Channels Module** | • Sockets and messages are strictly scoped to existing `Channel` entities.<br>• Cascade-deleted when a channel is deleted. | [app/channels/routes.py](../../backend/app/channels/routes.py) |
| **Database & Models** | • Persists to `messages` table with composite index on `(channel_id, created_at)`. | [app/models.py](../../backend/app/models.py) |

---

## 5. Technical Considerations

### 1. Mid-Session Demotion / Removal Protection
- **Design**: In standard WebSocket chat architectures, permissions are checked only during connection setup. If a malicious user is demoted to `read_only` or kicked from the channel, they could continue chatting until disconnect. The Chat module prevents this by querying `Membership` with `populate_existing=True` on every incoming frame.

### 2. Dual Token Extraction
- **Design**: Web browser JavaScript standard `new WebSocket(url)` does not allow custom headers (like `Authorization: Bearer`). The endpoint accepts the token via query parameters (`?token=...`) while still supporting `Authorization` headers for programmatic API clients.

### 3. Scalability & Clustering (Future Consideration)
- **Design**: The current `ChannelConnectionManager` manages sockets in-memory within a single server process. In a multi-worker or multi-container deployment, broadcasting between workers can be scaled horizontally by connecting `ChannelConnectionManager` to a Redis Pub/Sub backplane.
