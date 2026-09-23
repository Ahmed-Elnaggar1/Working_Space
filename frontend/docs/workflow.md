# Frontend Architecture & Component Workflow

This document illustrates the execution lifecycle, routing hierarchy, and component relationships currently implemented in the frontend application (`frontend/`).

---

## High-Level Lifecycle Diagram

```mermaid
flowchart TD
    %% Browser & Bootstrap
    Browser["🌐 Web Browser (URL Request)"] --> HTML["📄 index.html<br/>#40;mounts &lt;div id='root'&gt;#41;"]
    HTML --> Main["⚡ src/main.tsx<br/>#40;Entry Point#41;"]
    
    %% Global styling
    IndexCSS["🎨 src/index.css<br/>#40;Global Design Tokens, Theme &amp; Resets#41;"] -.->|Imports &amp; Injects| Main
    
    %% Root Component
    Main --> App["📦 src/App.tsx<br/>#40;Root Component#41;"]
    App --> RouterProvider["🔀 &lt;RouterProvider router={router} /&gt;"]
    
    %% Router
    RouterProvider --> Router["🛣️ src/routes/index.tsx<br/>#40;createBrowserRouter#41;"]
    
    %% Route Branches
    Router -->|Path: '/'| Redirect["↪️ &lt;Navigate to='/login' replace /&gt;"]
    Router -->|Path: '/login'| LoginPage["📄 LoginPage.tsx<br/>#40;S6-10 Placeholder#41;"]
    Router -->|Path: '/signup'| SignupPage["📄 SignupPage.tsx<br/>#40;S6-09 Placeholder#41;"]
    Router -->|Path: '/workspaces'| WorkspacesPage["📄 WorkspacesPage.tsx<br/>#40;S6-14/16 Placeholder#41;"]
    Router -->|Path: '*'| NotFoundPage["⚠️ NotFoundPage.tsx<br/>#40;404 Fallback#41;"]

    %% AuthLayout Subtree
    subgraph AuthSystem ["Reusable Auth System (Design System Layer)"]
        AuthLayout["🧱 src/components/AuthLayout/AuthLayout.tsx<br/>#40;Glassmorphic Card Shell, Logo &amp; Header#41;"]
        AuthCSS["🎨 AuthLayout.module.css<br/>#40;Glow, Inputs, Button &amp; Card Styles#41;"]
        AuthCSS -.->|Scoped Styles| AuthLayout
    end

    LoginPage -->|Renders within| AuthLayout
    SignupPage -->|Renders within| AuthLayout

    %% SPA Navigation
    LoginPage -.->|&lt;Link to='/signup'&gt;<br/>Client-side SPA Navigation| SignupPage
    SignupPage -.->|&lt;Link to='/login'&gt;<br/>Client-side SPA Navigation| LoginPage
    WorkspacesPage -.->|&lt;Link to='/login'&gt;| LoginPage
    NotFoundPage -.->|&lt;Link to='/'&gt;| Redirect
```

---

## Detailed Component & Route Breakdown

### 1. Bootstrapping Layer
- **`index.html`**: The HTML entry document containing `<div id="root"></div>`.
- **`src/main.tsx`**: Bootstraps React via `createRoot` inside `StrictMode` and applies `index.css`.
- **`src/index.css`**: Defines CSS design tokens (`--bg-app`, `--color-primary`, `--border-subtle`, glassmorphic variables, dark mode styling, and resets).

### 2. Application Shell & Routing Layer
- **`src/App.tsx`**: Mounts `<RouterProvider router={router} />`.
- **`src/routes/index.tsx`**: Instantiates `createBrowserRouter` defining route paths:
  - **`/`**: Default root redirect pointing to `/login` (will evaluate authentication state once token persistence is attached in S6-08/S6-11).
  - **`/login`**: Renders `LoginPage`.
  - **`/signup`**: Renders `SignupPage`.
  - **`/workspaces`**: Renders `WorkspacesPage`.
  - **`*`**: Catch-all path rendering `NotFoundPage`.

### 3. Reusable UI Components Layer
- **`src/components/AuthLayout/AuthLayout.tsx`**:
  - Reusable layout shell shared by `LoginPage` and `SignupPage`.
  - Renders the brand logo badge, title, subtitle, form slot (`children`), and footer navigation slot (`footer`).
  - Styled with **`AuthLayout.module.css`** (zero duplicate CSS across auth pages).

### 4. Pages Layer
- **`LoginPage` (`src/pages/LoginPage.tsx`)**:
  - Form with email and password inputs.
  - Client-side navigation link to `/signup`.
  - Ready for `POST /auth/login` integration (S6-10).
- **`SignupPage` (`src/pages/SignupPage.tsx`)**:
  - Form with email and password (minimum 8 characters) inputs.
  - Client-side navigation link to `/login`.
  - Ready for `POST /auth/signup` integration (S6-09).
- **`WorkspacesPage` (`src/pages/WorkspacesPage.tsx`)**:
  - Workspace list placeholder ready for `GET /workspaces` integration (S6-14/S6-16).
- **`NotFoundPage` (`src/pages/NotFoundPage.tsx`)**:
  - 404 page with navigation button back to `/`.
