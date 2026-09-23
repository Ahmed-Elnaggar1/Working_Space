import { useEffect, useState } from "react";
import { ApiError } from "../../../shared/api";
import { getChannel, getChannelMembers } from "../api";
import type { Channel, ChannelMember } from "../types";
import styles from "./ChannelShell.module.css";

interface ChannelShellProps {
  channelId: string;
}

export function ChannelShell({ channelId }: ChannelShellProps) {
  const [channel, setChannel] = useState<Channel | null>(null);
  const [members, setMembers] = useState<ChannelMember[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadChannel() {
      setIsLoading(true);
      setError(null);

      try {
        const [channelResult, membersResult] = await Promise.all([
          getChannel(channelId),
          getChannelMembers(channelId),
        ]);
        if (isMounted) {
          setChannel(channelResult);
          setMembers(membersResult);
        }
      } catch (loadError) {
        if (isMounted) {
          setError(
            loadError instanceof ApiError
              ? loadError.message
              : "Unable to load this channel. Please try again.",
          );
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadChannel();

    return () => {
      isMounted = false;
    };
  }, [channelId]);

  if (isLoading) {
    return <p className={styles.status}>Loading channel...</p>;
  }

  if (error) {
    return <p className={styles.error}>{error}</p>;
  }

  if (!channel) {
    return <p className={styles.error}>Channel not found.</p>;
  }

  return (
    <section className={styles.shell}>
      <p className={styles.eyebrow}>Channel</p>
      <h1>{channel.name}</h1>
      <div className={styles.section}>
        <h2>Members</h2>

        {members.length === 0 ? (
          <p className={styles.status}>No members found for this channel.</p>
        ) : (
          <ul className={styles.memberList}>
            {members.map((member) => (
              <li key={member.id} className={styles.memberItem}>
                <div>
                  <p className={styles.memberEmail}>{member.email}</p>
                </div>
                <span className={styles.roleBadge}>{member.role}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
