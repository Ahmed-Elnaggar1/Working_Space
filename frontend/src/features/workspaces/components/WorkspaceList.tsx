import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../../../shared/api";
import { getWorkspaces } from "../api";
import type { Workspace } from "../types";
import styles from "./WorkspaceList.module.css";

interface WorkspaceListProps {
  refreshKey: number;
}

export function WorkspaceList({ refreshKey }: WorkspaceListProps) {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadWorkspaces() {
      setIsLoading(true);
      setError(null);
      try {
        const result = await getWorkspaces();
        if (isMounted) {
          setWorkspaces(result);
        }
      } catch (loadError) {
        if (isMounted) {
          setError(
            loadError instanceof ApiError
              ? loadError.message
              : "Unable to load workspaces. Please try again.",
          );
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadWorkspaces();

    return () => {
      isMounted = false;
    };
  }, [refreshKey]);

  if (isLoading) {
    return <p className={styles.status}>Loading workspaces...</p>;
  }

  if (error) {
    return <p className={styles.error}>{error}</p>;
  }

  if (workspaces.length === 0) {
    return (
      <p className={styles.status}>
        You do not have access to any workspaces yet.
      </p>
    );
  }

  return (
    <ul className={styles.list}>
      {workspaces.map((workspace) => (
        <li className={styles.item} key={workspace.id}>
          <h2>
            <Link to={`/workspaces/${workspace.id}`}>{workspace.name}</Link>
          </h2>
          <p>Created {new Date(workspace.created_at).toLocaleDateString()}</p>
        </li>
      ))}
    </ul>
  );
}
