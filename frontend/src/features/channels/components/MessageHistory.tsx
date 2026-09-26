import { useEffect, useRef, useState } from "react";
import { ApiError } from "../../../shared/api";
import { getChannelMessages, postChannelMessage } from "../api";
import {
  getChatMessageActionErrorMessage,
  getSendFallbackNotice,
  type WebSocketConnectionStatus,
} from "../chatManagement";
import type { ChannelMember, ChannelMessage } from "../types";
import styles from "./MessageHistory.module.css";

interface MessageHistoryProps {
  channelId: string;
  members: ChannelMember[];
  currentUserId: string | undefined;
  socket: WebSocket | null;
  socketStatus?: WebSocketConnectionStatus;
  socketError?: string | null;
  canSendMessages: boolean;
}

export function MessageHistory({
  channelId,
  members,
  currentUserId,
  socket,
  socketStatus = "connecting",
  socketError = null,
  canSendMessages,
}: MessageHistoryProps) {
  const [messages, setMessages] = useState<ChannelMessage[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingOlder, setIsLoadingOlder] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [fallbackNotice, setFallbackNotice] = useState<string | null>(null);
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

  useEffect(() => {
    if (!socket) {
      return;
    }

    const handleIncomingMessage = (event: MessageEvent) => {
      try {
        const payload = JSON.parse(event.data) as Partial<ChannelMessage>;
        if (!payload || typeof payload.content !== "string" || !payload.id) {
          return;
        }

        const safePayload: ChannelMessage = {
          id: payload.id,
          channel_id: payload.channel_id ?? channelId,
          user_id: payload.user_id ?? currentUserId ?? "",
          content: payload.content,
          created_at: payload.created_at ?? new Date().toISOString(),
        };

        setMessages((currentMessages) => {
          if (
            currentMessages.some((message) => message.id === safePayload.id)
          ) {
            return currentMessages;
          }

          const localMatchIndex = currentMessages.findIndex(
            (message) =>
              message.id.startsWith("local-") &&
              message.user_id === safePayload.user_id &&
              message.content === safePayload.content &&
              Math.abs(
                Date.parse(message.created_at) -
                  Date.parse(safePayload.created_at),
              ) < 5000,
          );

          if (localMatchIndex >= 0) {
            const nextMessages = [...currentMessages];
            nextMessages[localMatchIndex] = safePayload;
            return nextMessages;
          }

          return [...currentMessages, safePayload];
        });
      } catch {
        // Ignore invalid or non-message socket payloads.
      }
    };

    socket.addEventListener("message", handleIncomingMessage);
    return () => {
      socket.removeEventListener("message", handleIncomingMessage);
    };
  }, [channelId, currentUserId, socket]);

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

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedContent = draft.trim();

    if (!trimmedContent || !canSendMessages || isSending) {
      return;
    }

    setDraft("");
    setIsSending(true);
    setSendError(null);

    const optimisticMessage: ChannelMessage = {
      id: `local-${Date.now()}`,
      channel_id: channelId,
      user_id: currentUserId ?? "",
      content: trimmedContent,
      created_at: new Date().toISOString(),
    };

    if (socket && socket.readyState === WebSocket.OPEN) {
      setFallbackNotice(null);
      setMessages((currentMessages) => [...currentMessages, optimisticMessage]);
      requestAnimationFrame(() => {
        if (scrollRef.current) {
          scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
      });

      try {
        socket.send(JSON.stringify({ content: trimmedContent }));
      } catch {
        setMessages((currentMessages) =>
          currentMessages.filter(
            (message) => message.id !== optimisticMessage.id,
          ),
        );
        setSendError("Failed to send message over socket. Please try again.");
      } finally {
        setIsSending(false);
      }
      return;
    }

    try {
      const createdMessage = await postChannelMessage(channelId, {
        content: trimmedContent,
      });
      setMessages((currentMessages) => [...currentMessages, createdMessage]);
      setFallbackNotice(getSendFallbackNotice());
      requestAnimationFrame(() => {
        if (scrollRef.current) {
          scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
      });
    } catch (sendErrorObject) {
      setSendError(getChatMessageActionErrorMessage(sendErrorObject));
    } finally {
      setIsSending(false);
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
        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {socketStatus === "disconnected" && !socketError && (
            <span
              className={styles.offlineNotice}
              data-testid="ws-disconnected-badge"
            >
              Real-time offline (HTTP fallback active)
            </span>
          )}
          {isLoadingOlder && (
            <span className={styles.loadingLabel}>Loading older...</span>
          )}
        </div>
      </div>

      {socketError && (
        <div
          className={styles.socketAlert}
          role="alert"
          data-testid="ws-rejection-notice"
        >
          <span aria-hidden="true">⚠️</span>
          <span>{socketError}</span>
        </div>
      )}

      {error && <p className={styles.error}>{error}</p>}
      {sendError && <p className={styles.error}>{sendError}</p>}
      {fallbackNotice && (
        <p
          className={styles.fallbackNotice}
          role="status"
          data-testid="fallback-send-notice"
        >
          ℹ️ {fallbackNotice}
        </p>
      )}

      {isLoading ? (
        <p className={styles.status}>Loading messages...</p>
      ) : (
        <>
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

          {canSendMessages ? (
            <form
              className={styles.composer}
              onSubmit={handleSubmit}
              data-testid="chat-composer-form"
            >
              <textarea
                className={styles.input}
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="Write a message..."
                rows={2}
                disabled={isSending}
                aria-label="Message input"
              />
              <button
                className={styles.sendButton}
                type="submit"
                disabled={isSending || draft.trim().length === 0}
              >
                {isSending ? "Sending..." : "Send"}
              </button>
            </form>
          ) : (
            <div
              className={styles.readOnlyNotice}
              data-testid="read-only-chat-notice"
            >
              <p>
                You have read-only permissions in this channel. You can view
                messages and ask the bot, but cannot send messages.
              </p>
            </div>
          )}
        </>
      )}
    </section>
  );
}
