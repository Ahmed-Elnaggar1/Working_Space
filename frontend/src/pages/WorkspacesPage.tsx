import { WorkspaceList } from "../features/workspaces/components/WorkspaceList";
import styles from "./WorkspacesPage.module.css";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../features/auth/useAuth";

export default function WorkspacesPage() {
  const navigate = useNavigate();
  const { logout, getErrorMessage } = useAuth();
  const [isLoggingOut, setIsLoggingOut] = useState(false);

  async function handleLogout() {
    setIsLoggingOut(true);

    try {
      await logout();
      navigate("/login", { replace: true });
    } catch (logoutError) {
      navigate("/login", {
        replace: true,
        state: { logoutError: getErrorMessage(logoutError) },
      });
    } finally {
      setIsLoggingOut(false);
    }
  }

  return (
    <div className={styles.page}>
      <main className={styles.content}>
        <header className={styles.header}>
          <h1>Workspaces</h1>
          <p>Choose a workspace to continue.</p>
          <div>
            <button
              type="button"
              className={styles.logoutButton}
              onClick={handleLogout}
              disabled={isLoggingOut}
            >
              {isLoggingOut ? "Signing out..." : "Sign out"}
            </button>
          </div>
        </header>
        <WorkspaceList />
      </main>
    </div>
  );
}
