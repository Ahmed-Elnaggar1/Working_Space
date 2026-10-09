import { useEffect, useRef, useState } from "react";
import { ApiError } from "../../../shared/api";
import {
  askChannel,
  downloadChannelFile,
  getChannelMessages,
  postChannelMessage,
} from "../api";
import {
  getChatMessageActionErrorMessage,
  getSendFallbackNotice,
  type WebSocketConnectionStatus,
  mergeRecentMessages,
} from "../chatManagement";
import {
  formatCitationLabel,
  getBotActionErrorMessage,
  isRetryableBotError,
} from "../bot";
import {
  appendCachedMessage,
  getCachedMessages,
  setCachedMessages,
} from "../channelCache";
import type {
  BotCitation,
  ChannelMember,
  ChannelMessage,
} from "../types";
import styles from "./MessageHistory.module.css";

export interface InlineBotResponse {
  id: string;
  userMessageId: string;
  question: string;
  status: "loading" | "success" | "insufficient_evidence" | "error";
  answer?: string;
  citations?: BotCitation[];
  errorMessage?: string;
  isRetryable?: boolean;
}

interface MessageHistoryProps {
  channelId: string;
  members: ChannelMember[];
  currentUserId: string | undefined;
  socket: WebSocket | null;
  socketStatus?: WebSocketConnectionStatus;
  socketError?: string | null;
  canSendMessages: boolean;
  canAskBot?: boolean;
  onOpenBotChat?: (initialQuestion?: string) => void;
  onOpenFileUpload?: () => void;
}

export function MessageHistory({
  channelId,
  members,
  currentUserId,
  socket,
  socketStatus = "connecting",
  socketError = null,
  canSendMessages,
  canAskBot = true,
  onOpenBotChat,
  onOpenFileUpload,
}: MessageHistoryProps) {
  // Initialize messages from in-memory cache if available
  const cachedData = getCachedMessages(channelId);
  const [messages, setMessages] = useState<ChannelMessage[]>(
    cachedData ? cachedData.items : [],
  );
  const [nextCursor, setNextCursor] = useState<string | null>(
    cachedData ? cachedData.nextCursor : null,
  );
  const [isLoading, setIsLoading] = useState(!cachedData);
  const [isLoadingOlder, setIsLoadingOlder] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sendError, setSendError] = useState<string | null>(null);
  const [fallbackNotice, setFallbackNotice] = useState<string | null>(null);
  const [inlineBotResponses, setInlineBotResponses] = useState<
    InlineBotResponse[]
  >([]);
  const [downloadingFileId, setDownloadingFileId] = useState<string | null>(
    null,
  );

  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const previousSocketStatusRef = useRef(socketStatus);

  // Sync state when channelId changes or cache updates
  useEffect(() => {
    const cached = getCachedMessages(channelId);
    if (cached) {
      setMessages(cached.items);
      setNextCursor(cached.nextCursor);
      setIsLoading(false);
    } else {
      setMessages([]);
      setNextCursor(null);
      setIsLoading(true);
    }
    setInlineBotResponses([]);
    setError(null);
    setSendError(null);
    setFallbackNotice(null);
  }, [channelId]);

  // Load initial messages from API (or refresh in background)
  useEffect(() => {
    let isMounted = true;

    async function loadInitialMessages() {
      // If we don't have cache, set loading
      const cached = getCachedMessages(channelId);
      if (!cached) {
        setIsLoading(true);
      }
      setError(null);

      try {
        const page = await getChannelMessages(channelId);
        if (isMounted) {
          setMessages(page.items);
          setNextCursor(page.next_cursor);
          setCachedMessages(channelId, page.items, page.next_cursor);
          requestAnimationFrame(() => {
            if (scrollRef.current) {
              scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
            }
          });
        }
      } catch (loadError) {
        if (isMounted && !cached) {
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

  // Socket reconnect gap filling
  useEffect(() => {
    const didReconnect =
      previousSocketStatusRef.current === "disconnected" &&
      socketStatus === "connected";
    previousSocketStatusRef.current = socketStatus;

    if (!didReconnect) {
      return;
    }

    let isMounted = true;
    async function fillReconnectGap() {
      try {
        const page = await getChannelMessages(channelId);
        if (isMounted) {
          setMessages((currentMessages) => {
            const merged = mergeRecentMessages(currentMessages, page.items);
            setCachedMessages(channelId, merged, page.next_cursor);
            return merged;
          });
          setNextCursor((currentCursor) => currentCursor ?? page.next_cursor);
        }
      } catch {
        if (isMounted) {
          setError("Unable to refresh messages after reconnecting.");
        }
      }
    }

    void fillReconnectGap();
    return () => {
      isMounted = false;
    };
  }, [channelId, socketStatus]);

  // Handle incoming real-time socket messages
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

          let updated: ChannelMessage[];
          if (localMatchIndex >= 0) {
            updated = [...currentMessages];
            updated[localMatchIndex] = safePayload;
          } else {
            updated = [...currentMessages, safePayload];
          }

          setCachedMessages(channelId, updated, nextCursor);
          return updated;
        });

        // Trigger bot if someone mentioned @bot in the received message
        if (
          canAskBot &&
          safePayload.content.toLowerCase().includes("@bot") &&
          safePayload.user_id !== "bot"
        ) {
          triggerInlineBot(safePayload.id, safePayload.content);
        }

        requestAnimationFrame(() => {
          if (scrollRef.current) {
            scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
          }
        });
      } catch {
        // Ignore invalid socket payloads
      }
    };

    socket.addEventListener("message", handleIncomingMessage);
    return () => {
      socket.removeEventListener("message", handleIncomingMessage);
    };
  }, [channelId, currentUserId, nextCursor, socket, canAskBot]);

  async function loadOlderMessages() {
    if (!nextCursor || isLoadingOlder || !scrollRef.current) {
      return;
    }

    const scrollContainer = scrollRef.current;
    const previousScrollHeight = scrollContainer.scrollHeight;
    setIsLoadingOlder(true);

    try {
      const page = await getChannelMessages(channelId, nextCursor);
      setMessages((currentMessages) => {
        const merged = [...page.items, ...currentMessages];
        setCachedMessages(channelId, merged, page.next_cursor);
        return merged;
      });
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

  // Trigger inline bot query when @bot is mentioned
  async function triggerInlineBot(
    userMessageId: string,
    messageContent: string,
    retryResponseId?: string,
  ) {
    const questionText = messageContent.replace(/@bot\b/gi, "").trim() || messageContent;
    const responseId =
      retryResponseId ??
      `inline-bot-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

    const pendingItem: InlineBotResponse = {
      id: responseId,
      userMessageId,
      question: questionText,
      status: "loading",
    };

    if (retryResponseId) {
      setInlineBotResponses((prev) =>
        prev.map((item) => (item.id === retryResponseId ? pendingItem : item)),
      );
    } else {
      setInlineBotResponses((prev) => [...prev, pendingItem]);
    }

    try {
      // Build recent conversation context for LLM
      const apiHistory = messages.slice(-5).map((m) => ({
        role: m.content.toLowerCase().includes("@bot") ? "user" : "user",
        content: m.content,
      }));

      const res = await askChannel(channelId, questionText, apiHistory);

      setInlineBotResponses((prev) =>
        prev.map((item) => {
          if (item.id !== responseId) return item;
          if (res.insufficient_evidence) {
            return {
              ...item,
              status: "insufficient_evidence",
              answer: res.answer,
              citations: [],
            };
          }
          return {
            ...item,
            status: "success",
            answer: res.answer,
            citations: res.citations,
          };
        }),
      );
    } catch (askError) {
      const errorMessage = getBotActionErrorMessage(askError);
      const isRetryable = isRetryableBotError(askError);
      setInlineBotResponses((prev) =>
        prev.map((item) =>
          item.id === responseId
            ? {
                ...item,
                status: "error",
                errorMessage,
                isRetryable,
              }
            : item,
        ),
      );
    } finally {
      requestAnimationFrame(() => {
        if (scrollRef.current) {
          scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
      });
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

    const isBotMention = trimmedContent.toLowerCase().includes("@bot");
    const optimisticId = `local-${Date.now()}`;
    const optimisticMessage: ChannelMessage = {
      id: optimisticId,
      channel_id: channelId,
      user_id: currentUserId ?? "",
      content: trimmedContent,
      created_at: new Date().toISOString(),
    };

    if (socket && socket.readyState === WebSocket.OPEN) {
      setFallbackNotice(null);
      setMessages((currentMessages) => {
        const next = [...currentMessages, optimisticMessage];
        appendCachedMessage(channelId, optimisticMessage);
        return next;
      });

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

      if (isBotMention && canAskBot) {
        void triggerInlineBot(optimisticId, trimmedContent);
      }
      return;
    }

    // HTTP Fallback
    try {
      const createdMessage = await postChannelMessage(channelId, {
        content: trimmedContent,
      });
      setMessages((currentMessages) => {
        const next = [...currentMessages, createdMessage];
        appendCachedMessage(channelId, createdMessage);
        return next;
      });
      setFallbackNotice(getSendFallbackNotice());
      requestAnimationFrame(() => {
        if (scrollRef.current) {
          scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
        }
      });

      if (isBotMention && canAskBot) {
        void triggerInlineBot(createdMessage.id, trimmedContent);
      }
    } catch (sendErrorObject) {
      setSendError(getChatMessageActionErrorMessage(sendErrorObject));
    } finally {
      setIsSending(false);
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      const fakeEvent = { preventDefault: () => {} } as React.FormEvent<HTMLFormElement>;
      void handleSubmit(fakeEvent);
    }
  }

  function insertBotMention() {
    setDraft((prev) => {
      const prefix = prev.trim().length > 0 ? `${prev.trim()} ` : "";
      return `${prefix}@bot `;
    });
    textareaRef.current?.focus();
  }

  async function handleDownloadCitation(citation: BotCitation) {
    setDownloadingFileId(citation.file_id);
    try {
      await downloadChannelFile(channelId, citation.file_id, citation.file_name);
    } catch {
      // Ignore
    } finally {
      setDownloadingFileId(null);
    }
  }

  function getSenderName(userId: string): string {
    const member = members.find((candidate) => candidate.user_id === userId);
    if (!member) {
      return userId || "Anonymous";
    }
    return member.username ?? member.email;
  }

  function getSenderInitials(userId: string): string {
    const name = getSenderName(userId);
    return name.slice(0, 2).toUpperCase();
  }

  return (
    <section className={styles.history} aria-labelledby="message-history-title">
      <div className={styles.header}>
        <div className={styles.headerMeta}>
          <p className={styles.eyebrow}>Conversation</p>
          <h2 id="message-history-title">Message history</h2>
        </div>
        <div className={styles.headerActions}>
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

      {/* Message List or Skeleton */}
      <div
        ref={scrollRef}
        className={styles.messageList}
        onScroll={handleScroll}
        aria-label="Channel messages"
      >
        {isLoading ? (
          <div className={styles.skeletonContainer}>
            <div className={styles.skeletonMessage}>
              <div className={styles.skeletonAvatar} />
              <div className={styles.skeletonLines}>
                <div className={styles.skeletonLineShort} />
                <div className={styles.skeletonLineLong} />
              </div>
            </div>
            <div className={styles.skeletonMessage}>
              <div className={styles.skeletonAvatar} />
              <div className={styles.skeletonLines}>
                <div className={styles.skeletonLineShort} />
                <div className={styles.skeletonLineLong} />
              </div>
            </div>
            <div className={styles.skeletonMessage}>
              <div className={styles.skeletonAvatar} />
              <div className={styles.skeletonLines}>
                <div className={styles.skeletonLineShort} />
                <div className={styles.skeletonLineMedium} />
              </div>
            </div>
          </div>
        ) : messages.length === 0 ? (
          <div className={styles.emptyMessages}>
            <span className={styles.emptyIcon}>💬</span>
            <p className={styles.status}>No messages in this channel yet.</p>
            <p className={styles.emptySubtext}>
              Be the first to say hello or ask <strong>@bot</strong> a question about channel files!
            </p>
          </div>
        ) : (
          messages.map((message) => {
            const botResponse = inlineBotResponses.find(
              (res) => res.userMessageId === message.id,
            );

            return (
              <div key={message.id} className={styles.messageGroup}>
                <article className={styles.message}>
                  <div className={styles.avatar}>
                    {getSenderInitials(message.user_id)}
                  </div>
                  <div className={styles.messageBody}>
                    <div className={styles.messageMeta}>
                      <strong className={styles.senderName}>
                        {getSenderName(message.user_id)}
                      </strong>
                      <time
                        dateTime={message.created_at}
                        className={styles.timestamp}
                      >
                        {new Date(message.created_at).toLocaleTimeString([], {
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </time>
                    </div>
                    <p className={styles.messageText}>{message.content}</p>
                  </div>
                </article>

                {/* Inline Bot Response Card if @bot was mentioned */}
                {botResponse && (
                  <div className={styles.inlineBotCard}>
                    <div className={styles.botCardHeader}>
                      <div className={styles.botBadge}>
                        <span aria-hidden="true">🤖</span>
                        <span>Assistant</span>
                      </div>
                      <span className={styles.botRespondingTo}>
                        Replying to @bot mention
                      </span>
                    </div>

                    {botResponse.status === "loading" && (
                      <div className={styles.botLoading}>
                        <div className={styles.botSpinner} />
                        <span>Searching channel documents and reasoning...</span>
                      </div>
                    )}

                    {botResponse.status === "insufficient_evidence" && (
                      <div className={styles.botEvidenceWarning}>
                        <p>
                          ℹ️ No sufficient evidence found in this channel&apos;s
                          ingested files to answer this question.
                        </p>
                      </div>
                    )}

                    {botResponse.status === "success" && (
                      <div className={styles.botAnswerContent}>
                        <p className={styles.botAnswerText}>
                          {botResponse.answer}
                        </p>
                        {botResponse.citations &&
                          botResponse.citations.length > 0 && (
                            <div className={styles.citationsRow}>
                              <span className={styles.sourcesLabel}>Sources:</span>
                              {botResponse.citations.map((c, idx) => (
                                <button
                                  key={`${c.file_id}-${c.page}-${idx}`}
                                  type="button"
                                  className={styles.citationPill}
                                  onClick={() => void handleDownloadCitation(c)}
                                  disabled={downloadingFileId === c.file_id}
                                >
                                  📄 {formatCitationLabel(c)}
                                </button>
                              ))}
                            </div>
                          )}
                        {onOpenBotChat && (
                          <button
                            type="button"
                            className={styles.openBotChatBtn}
                            onClick={() => onOpenBotChat(botResponse.question)}
                          >
                            Continue in Bot Assistant →
                          </button>
                        )}
                      </div>
                    )}

                    {botResponse.status === "error" && (
                      <div className={styles.botErrorCard}>
                        <p>⚠️ {botResponse.errorMessage || "Bot query failed."}</p>
                        {botResponse.isRetryable && (
                          <button
                            type="button"
                            className={styles.retryBotBtn}
                            onClick={() =>
                              void triggerInlineBot(
                                message.id,
                                message.content,
                                botResponse.id,
                              )
                            }
                          >
                            Retry
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Composer Area */}
      {canSendMessages ? (
        <form
          className={styles.composer}
          onSubmit={handleSubmit}
          data-testid="chat-composer-form"
        >
          {/* Quick Toolbar above input */}
          <div className={styles.composerToolbar}>
            <button
              type="button"
              className={styles.botMentionChip}
              onClick={insertBotMention}
              title="Insert @bot mention into draft"
            >
              <span>🤖</span>
              <span>Ask @bot</span>
            </button>
            {onOpenFileUpload && (
              <button
                type="button"
                className={styles.attachmentButton}
                onClick={onOpenFileUpload}
                title="Upload file to channel"
              >
                <span>📎</span>
                <span>Attach File</span>
              </button>
            )}
            <span className={styles.shortcutHint}>
              Press <kbd>Enter</kbd> to send, <kbd>Shift+Enter</kbd> for newline
            </span>
          </div>

          <div className={styles.inputWrapper}>
            <textarea
              ref={textareaRef}
              className={styles.input}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Message #channel or type @bot to ask documents..."
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
          </div>
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
    </section>
  );
}
