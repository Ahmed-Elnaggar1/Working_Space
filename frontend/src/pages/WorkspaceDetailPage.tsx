import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CreateChannelForm } from "../features/workspaces/components/CreateChannelForm";
import { WorkspaceDetail } from "../features/workspaces/components/WorkspaceDetail";
import styles from "./WorkspaceDetailPage.module.css";

export default function WorkspaceDetailPage() {
  const { workspaceId } = useParams();
  const [channelRefreshKey, setChannelRefreshKey] = useState(0);

  if (!workspaceId) {
    return <p>Workspace ID is missing.</p>;
  }

  return (
    <div className={styles.page}>
      <main className={styles.content}>
        <Link to="/workspaces">Back to workspaces</Link>
        <CreateChannelForm
          workspaceId={workspaceId}
          onCreated={() => setChannelRefreshKey((key) => key + 1)}
        />
        <WorkspaceDetail
          workspaceId={workspaceId}
          refreshKey={channelRefreshKey}
        />
      </main>
    </div>
  );
}
