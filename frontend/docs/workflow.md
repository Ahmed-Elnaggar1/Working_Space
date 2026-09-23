# Frontend Architecture & Component Workflow

This document illustrates the complete execution lifecycle, routing hierarchy, state flow, and component relationships in the frontend application (`frontend/`).

---

## 1. High-Level Lifecycle & Workflow Diagram

```mermaid
flowchart TD
    %% Browser & HTML Shell
    subgraph Bootstrap ["1. Bootstrapping Layer"]
        Browser["🌐 Web Browser (URL Request)"] --> HTML["📄 index.html<br/>(Mount point: &lt;div id='root'&gt;)"]
        HTML --> Main["⚡ src/main.tsx<br/>(createRoot &amp; StrictMode)"]
        IndexCSS["🎨 src/index.css<br/>(Global CSS Tokens &amp; Theme)"] -.->|Injected globally| Main
    end

    %% Root & Providers
    subgraph RootLayer ["2. Application Shell & State Providers"]
        Main --> App["📦 src/app/App.tsx<br/>(Root Application Component)"]
        App --> AuthProvider["🔐 src/features/auth/AuthProvider.tsx<br/>(Manages User Session, Tokens, Login/Logout)"]
        AuthProvider --> RouterProvider["🔀 &lt;RouterProvider router={router} /&gt;<br/>(React Router v7)"]
    end

    %% Router Layer
    subgraph RoutingLayer ["3. Routing Engine (src/app/router.tsx)"]
        RouterProvider --> Router["🛣️ createBrowserRouter(...)"]
        
        %% Public Routes
        Router -->|Path: '/'| Redirect["↪️ &lt;Navigate to='/login' replace /&gt;"]
        Router -->|Path: '/login'| LoginPage["📄 src/pages/LoginPage.tsx"]
        Router -->|Path: '/signup'| SignupPage["📄 src/pages/SignupPage.tsx"]
        Router -->|Path: '*'| NotFoundPage["⚠️ src/pages/NotFoundPage.tsx (404)"]

        %% Protected Routes
        Router -->|Protected Subtree| ProtectedRoute["🛡️ src/features/auth/components/ProtectedRoute.tsx<br/>(Checks isAuthenticated &amp; isLoading)"]
        ProtectedRoute -->|Auth OK &lt;Outlet /&gt;| WorkspacesPage["📄 src/pages/WorkspacesPage.tsx"]
        ProtectedRoute -->|Auth OK &lt;Outlet /&gt;| WorkspaceDetailPage["📄 src/pages/WorkspaceDetailPage.tsx"]
        ProtectedRoute -->|Auth OK &lt;Outlet /&gt;| ChannelDetailPage["📄 src/pages/ChannelDetailPage.tsx"]
        ProtectedRoute -.->|Not Authenticated| RedirectLogin["↪️ &lt;Navigate to='/login' /&gt;"]
    end

    %% Component & Layout Layer
    subgraph ComponentsLayer ["4. Feature & Layout Components"]
        LoginPage --> AuthLayout["🧱 src/shared/layouts/AuthLayout<br/>(Glassmorphic Card &amp; Header)"]
        SignupPage --> AuthLayout
        
        LoginPage --> LoginForm["📝 LoginForm.tsx"]
        SignupPage --> SignupForm["📝 SignupForm.tsx"]

        WorkspacesPage --> WorkspaceList["📋 WorkspaceList.tsx"]
        WorkspacesPage --> CreateWorkspaceForm["➕ CreateWorkspaceForm.tsx"]

        WorkspaceDetailPage --> WorkspaceDetail["🏢 WorkspaceDetail.tsx"]
        WorkspaceDetailPage --> CreateChannelForm["➕ CreateChannelForm.tsx"]

        ChannelDetailPage --> ChannelShell["💬 ChannelShell.tsx"]
    end

    %% Shared API & Services
    subgraph ApiLayer ["5. Shared API & Network Layer"]
        LoginForm -.->|login| AuthApi["src/features/auth/api.ts"]
        SignupForm -.->|signup| AuthApi
        WorkspaceList -.->|fetchWorkspaces| WorkspacesApi["src/features/workspaces/api.ts"]
        CreateWorkspaceForm -.->|createWorkspace| WorkspacesApi
        CreateChannelForm -.->|createChannel| ChannelsApi["src/features/channels/api.ts"]

        AuthApi --> ApiClient["🌐 src/shared/api/client.ts<br/>(Fetch wrapper + Bearer token interceptor)"]
        WorkspacesApi --> ApiClient
        ChannelsApi --> ApiClient
    end
```

---

## 2. Layer-by-Layer Overview

### Layer 1: Bootstrapping
- **`index.html`**: The single HTML page downloaded by the browser. Contains `<div id="root"></div>` where React takes control.
- **`src/main.tsx`**: The JavaScript/TypeScript starting file. Uses React 19's `createRoot()` to mount `<App />` into the DOM.
- **`src/index.css`**: Global design system variables (colors, borders, gradients, glassmorphism) and CSS reset.

### Layer 2: State Providers & App Shell
- **`src/app/App.tsx`**: Composes high-level context providers.
- **`AuthProvider` (`src/features/auth/AuthProvider.tsx`)**: Wraps the whole app so any component can access the logged-in user, authentication status, and login/logout handlers via the `useAuth()` hook.
- **`RouterProvider`**: Connects React Router to render views based on the current URL.

### Layer 3: Routing Engine
- **`src/app/router.tsx`**:
  - **Public routes**: `/login`, `/signup`, and default `/` redirect.
  - **Protected routes**: Enclosed in `<ProtectedRoute />`. If a user is not authenticated, they get redirected to `/login`.
  - **Fallbacks**: Any undefined URL matches `*` to show `NotFoundPage`.

### Layer 4: Feature Components & Layouts
- **Feature-driven folders (`src/features/`)**:
  - `auth`: `LoginForm`, `SignupForm`, `ProtectedRoute`, `useAuth`, `AuthProvider`.
  - `workspaces`: `WorkspaceList`, `CreateWorkspaceForm`, `WorkspaceDetail`.
  - `channels`: `ChannelShell`, `CreateChannelForm`.
- **Reusable Layouts (`src/shared/layouts/`)**: Shared shells like `AuthLayout`.

### Layer 5: Data & API Client
- **`src/shared/api/client.ts`**: Standardized HTTP client wrapping browser `fetch`. Automatically attaches authorization tokens from `AuthProvider` and normalizes API error responses.
