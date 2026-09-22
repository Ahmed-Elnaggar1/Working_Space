import { useEffect, useState } from "react";
import { ApiError } from "../../../shared/api";
import { getWorkspace, getWorkspaceChannels } from "../api";
import type { Channel, Workspace } from "../types";
import styles from "./WorkspaceDetail.module.css";

interface WorkspaceDetailProps {
  workspaceId: string;
  refreshKey: number;
}

export function WorkspaceDetail({
  workspaceId,
  refreshKey,
}: WorkspaceDetailProps) {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadWorkspace() {
      setIsLoading(true);
      setError(null);

      try {
        const [workspaceResult, channelResult] = await Promise.all([
          getWorkspace(workspaceId),
          getWorkspaceChannels(workspaceId),
        ]);

        if (isMounted) {
          setWorkspace(workspaceResult);
          setChannels(channelResult);
        }
      } catch (loadError) {
        if (isMounted) {
          setError(
            loadError instanceof ApiError
              ? loadError.message
              : "Unable to load this workspace. Please try again.",
          );
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadWorkspace();

    return () => {
      isMounted = false;
    };
  }, [workspaceId, refreshKey]);

  if (isLoading) {
    return <p className={styles.status}>Loading workspace...</p>;
  }

  if (error) {
    return <p className={styles.error}>{error}</p>;
  }

  if (!workspace) {
    return <p className={styles.error}>Workspace not found.</p>;
  }

  return (
    <section>
      <header className={styles.header}>
        <h1>{workspace.name}</h1>
        <p>Channels you can access in this workspace.</p>
      </header>

      {channels.length === 0 ? (
        <p className={styles.status}>You do not belong to any channels yet.</p>
      ) : (
        <ul className={styles.list}>
          {channels.map((channel) => (
            <li className={styles.item} key={channel.id}>
              <h2>{channel.name}</h2>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
