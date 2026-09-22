import { useEffect, useState } from "react";
import { ApiError } from "../../../shared/api";
import { getChannel } from "../api";
import type { Channel } from "../types";
import styles from "./ChannelShell.module.css";

interface ChannelShellProps {
  channelId: string;
}

export function ChannelShell({ channelId }: ChannelShellProps) {
  const [channel, setChannel] = useState<Channel | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadChannel() {
      setIsLoading(true);
      setError(null);

      try {
        const result = await getChannel(channelId);
        if (isMounted) {
          setChannel(result);
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
      <p className={styles.status}>
        This channel is ready for files, chat, and bot features in future
        sprints.
      </p>
    </section>
  );
}
