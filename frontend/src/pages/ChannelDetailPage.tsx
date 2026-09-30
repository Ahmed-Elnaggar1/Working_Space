import { Link, useParams } from "react-router-dom";
import { ChannelShell } from "../features/channels/components/ChannelShell";
import styles from "./ChannelDetailPage.module.css";

export default function ChannelDetailPage() {
  const { channelId } = useParams();

  if (!channelId) {
    return <p>Channel ID is missing.</p>;
  }

  return (
    <div className={styles.page}>
      <main className={styles.content}>
        <Link to="/workspaces">Back to workspaces</Link>
        <ChannelShell channelId={channelId} />
      </main>
    </div>
  );
}
