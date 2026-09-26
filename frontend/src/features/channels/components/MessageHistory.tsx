import { useEffect, useRef, useState } from "react";
import { ApiError } from "../../../shared/api";
import { getChannelMessages } from "../api";
import type { ChannelMember, ChannelMessage } from "../types";
import styles from "./MessageHistory.module.css";

interface MessageHistoryProps {
  channelId: string;
  members: ChannelMember[];
  currentUserId: string | undefined;
}

export function MessageHistory({
  channelId,
  members,
  currentUserId,
}: MessageHistoryProps) {
  const [messages, setMessages] = useState<ChannelMessage[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingOlder, setIsLoadingOlder] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadInitialMessages() {
      setIsLoading(true);
      setError(null);

      try {
        const page = await getChannelMessages(channelId);
        if (isMounted) {
          setMessages(page.items);
          setNextCursor(page.next_cursor);
          requestAnimationFrame(() => {
            if (scrollRef.current) {
              scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
            }
          });
        }
      } catch (loadError) {
        if (isMounted) {
          setError(
            loadError instanceof ApiError
              ? loadError.message
              : "Unable to load message history. Please try again.",
          );
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    void loadInitialMessages();

    return () => {
      isMounted = false;
    };
  }, [channelId]);

  async function loadOlderMessages() {
    if (!nextCursor || isLoadingOlder || !scrollRef.current) {
      return;
    }

    const scrollContainer = scrollRef.current;
    const previousScrollHeight = scrollContainer.scrollHeight;
    setIsLoadingOlder(true);

    try {
      const page = await getChannelMessages(channelId, nextCursor);
      setMessages((currentMessages) => [...page.items, ...currentMessages]);
      setNextCursor(page.next_cursor);
      requestAnimationFrame(() => {
        if (scrollRef.current) {
          scrollRef.current.scrollTop +=
            scrollRef.current.scrollHeight - previousScrollHeight;
        }
      });
    } catch (loadError) {
      setError(
        loadError instanceof ApiError
          ? loadError.message
          : "Unable to load older messages. Please try again.",
      );
    } finally {
      setIsLoadingOlder(false);
    }
  }

  function handleScroll() {
    if (scrollRef.current && scrollRef.current.scrollTop <= 24) {
      void loadOlderMessages();
    }
  }

  function getSenderName(userId: string): string {
    const member = members.find((candidate) => candidate.user_id === userId);
    if (!member) {
      return userId;
    }
    return userId === currentUserId ? `${member.email} (You)` : member.email;
  }

  return (
    <section className={styles.history} aria-labelledby="message-history-title">
      <div className={styles.header}>
        <div>
          <p className={styles.eyebrow}>Conversation</p>
          <h2 id="message-history-title">Message history</h2>
        </div>
        {isLoadingOlder && (
          <span className={styles.loadingLabel}>Loading older...</span>
        )}
      </div>

      {error && <p className={styles.error}>{error}</p>}

      {isLoading ? (
        <p className={styles.status}>Loading messages...</p>
      ) : (
        <div
          ref={scrollRef}
          className={styles.messageList}
          onScroll={handleScroll}
          aria-label="Channel messages"
        >
          {messages.length === 0 ? (
            <p className={styles.status}>No messages in this channel yet.</p>
          ) : (
            messages.map((message) => (
              <article key={message.id} className={styles.message}>
                <div className={styles.messageMeta}>
                  <strong>{getSenderName(message.user_id)}</strong>
                  <time dateTime={message.created_at}>
                    {new Date(message.created_at).toLocaleString()}
                  </time>
                </div>
                <p>{message.content}</p>
              </article>
            ))
          )}
        </div>
      )}
    </section>
  );
}
