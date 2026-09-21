import { Link, useParams } from "react-router-dom";
import { WorkspaceDetail } from "../features/workspaces/components/WorkspaceDetail";
import styles from "./WorkspaceDetailPage.module.css";

export default function WorkspaceDetailPage() {
  const { workspaceId } = useParams();

  if (!workspaceId) {
    return <p>Workspace ID is missing.</p>;
  }

  return (
    <div className={styles.page}>
      <main className={styles.content}>
        <Link to="/workspaces">Back to workspaces</Link>
        <WorkspaceDetail workspaceId={workspaceId} />
      </main>
    </div>
  );
}
