import { WorkspaceList } from "../features/workspaces/components/WorkspaceList";
import styles from "./WorkspacesPage.module.css";

export default function WorkspacesPage() {
  return (
    <div className={styles.page}>
      <main className={styles.content}>
        <header className={styles.header}>
          <h1>Workspaces</h1>
          <p>Choose a workspace to continue.</p>
        </header>
        <WorkspaceList />
      </main>
    </div>
  );
}
