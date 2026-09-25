import React, { useEffect, useRef, useState } from "react";
import { askChannel, downloadChannelFile } from "../api";
import {
  clearSessionAskHistory,
  formatCitationLabel,
  getBotActionErrorMessage,
  isRetryableBotError,
  loadSessionAskHistory,
  LONG_WAIT_THRESHOLD_MS,
  MAX_QUESTION_LENGTH,
  saveSessionAskHistory,
  validateQuestion,
} from "../bot";
import type { BotCitation, BotQAPair } from "../types";
import styles from "./BotAskPanel.module.css";

function generateQaId(): string {
  return `qa-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

interface BotAskPanelProps {
  channelId: string;
}

export function BotAskPanel({ channelId }: BotAskPanelProps) {
  const [history, setHistory] = useState<BotQAPair[]>(() =>
    loadSessionAskHistory(channelId),
  );
  const [question, setQuestion] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isLongWaiting, setIsLongWaiting] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [downloadingFileId, setDownloadingFileId] = useState<string | null>(
    null,
  );
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const historyEndRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<number | null>(null);

  // Persist history to session storage
  useEffect(() => {
    saveSessionAskHistory(channelId, history);
  }, [channelId, history]);

  // Clean up timer on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
      }
    };
  }, []);

  async function executeAsk(questionText: string, existingId?: string) {
    const trimmed = questionText.trim();
    const validation = validateQuestion(trimmed);
    if (!validation.valid) {
      setValidationError(validation.error ?? "Invalid question.");
      return;
    }

    setValidationError(null);
    setDownloadError(null);

    const qaId = existingId ?? generateQaId();
    const nowIso = new Date().toISOString();

    const pendingPair: BotQAPair = {
      id: qaId,
      question: trimmed,
      status: "loading",
      createdAt: nowIso,
    };

    if (existingId) {
      setHistory((prev) =>
        prev.map((item) => (item.id === existingId ? pendingPair : item)),
      );
    } else {
      setHistory((prev) => [...prev, pendingPair]);
      setQuestion("");
    }

    setIsLoading(true);
    setIsLongWaiting(false);

    // S8-07: Show a "still working" notice if the LLM call takes longer than threshold
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
    }
    timerRef.current = window.setTimeout(() => {
      setIsLongWaiting(true);
    }, LONG_WAIT_THRESHOLD_MS);

    try {
      const response = await askChannel(channelId, trimmed);

      setHistory((prev) =>
        prev.map((item) => {
          if (item.id !== qaId) return item;

          if (response.insufficient_evidence) {
            // S8-09: Distinct honest insufficient evidence state
            return {
              ...item,
              status: "insufficient_evidence",
              answer: response.answer,
              citations: [],
              insufficient_evidence: true,
            };
          }

          // S8-08: Success with answer and citations
          return {
            ...item,
            status: "success",
            answer: response.answer,
            citations: response.citations,
            insufficient_evidence: false,
          };
        }),
      );
    } catch (askError) {
      // S8-10: Graceful retryable error handling
      const errorMessage = getBotActionErrorMessage(askError);
      const isRetryable = isRetryableBotError(askError);

      setHistory((prev) =>
        prev.map((item) =>
          item.id === qaId
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
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      setIsLoading(false);
      setIsLongWaiting(false);

      // Scroll to bottom of conversation
      setTimeout(() => {
        historyEndRef.current?.scrollIntoView({ behavior: "smooth" });
      }, 50);
    }
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (isLoading) return;
    void executeAsk(question);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!isLoading && question.trim().length > 0) {
        void executeAsk(question);
      }
    }
  }

  function handleRetry(qaItem: BotQAPair) {
    if (isLoading) return;
    void executeAsk(qaItem.question, qaItem.id);
  }

  function handleClearHistory() {
    clearSessionAskHistory(channelId);
    setHistory([]);
  }

  async function handleDownloadCitation(citation: BotCitation) {
    setDownloadingFileId(citation.file_id);
    setDownloadError(null);
    try {
      await downloadChannelFile(
        channelId,
        citation.file_id,
        citation.file_name,
      );
    } catch {
      setDownloadError(
        `Failed to download ${citation.file_name}. The file may no longer be available.`,
      );
    } finally {
      setDownloadingFileId(null);
    }
  }

  const remainingChars = MAX_QUESTION_LENGTH - question.length;

  return (
    <div className={styles.container} aria-label="Channel search bot panel">
      {/* Header */}
      <div className={styles.header}>
        <div>
          <div className={styles.headerTitle}>
            <span className={styles.botIcon} aria-hidden="true">
              🤖
            </span>
            <span>Ask Bot</span>
          </div>
          <p className={styles.headerSubtitle}>
            Ask questions grounded strictly in this channel&apos;s ingested
            materials.
          </p>
        </div>

        {history.length > 0 && (
          <button
            type="button"
            className={styles.clearButton}
            onClick={handleClearHistory}
            disabled={isLoading}
            title="Clear Q&A history for this browser session"
          >
            Clear history
          </button>
        )}
      </div>

      {downloadError && (
        <div className={styles.errorCard} role="alert">
          <p className={styles.errorText}>{downloadError}</p>
        </div>
      )}

      {/* S8-11: Running list of session Q&A */}
      <div className={styles.historyList}>
        {history.length === 0 ? (
          <div className={styles.emptyState}>
            <p className={styles.emptyStateTitle}>No questions asked yet</p>
            <p className={styles.emptyStateText}>
              Ask questions about the files uploaded to this channel. The bot
              returns grounded answers with direct document and page citations.
            </p>
          </div>
        ) : (
          history.map((qaItem) => (
            <div key={qaItem.id} className={styles.qaCard}>
              {/* Question Row */}
              <div className={styles.questionRow}>
                <span className={styles.userBadge}>You</span>
                <div className={styles.questionContent}>
                  <p className={styles.questionText}>{qaItem.question}</p>
                  <p className={styles.timestamp}>
                    {new Date(qaItem.createdAt).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                </div>
              </div>

              {/* Bot Response Row */}
              <div className={styles.answerRow}>
                <span className={styles.botBadge}>Bot</span>
                <div className={styles.answerContent}>
                  {/* S8-07: Loading State */}
                  {qaItem.status === "loading" && (
                    <div className={styles.loadingContainer}>
                      <div className={styles.spinnerRow}>
                        <div
                          className={styles.spinner}
                          aria-label="Loading answer"
                        />
                        <span>Searching channel documents & generating answer...</span>
                      </div>
                      {isLongWaiting && (
                        <p className={styles.longWaitNotice}>
                          Still working, analyzing materials with the AI model...
                        </p>
                      )}
                    </div>
                  )}

                  {/* S8-09: Insufficient Evidence */}
                  {qaItem.status === "insufficient_evidence" && (
                    <div
                      className={styles.insufficientCard}
                      role="status"
                      aria-live="polite"
                    >
                      <div className={styles.insufficientHeader}>
                        <span aria-hidden="true">ℹ️</span>
                        <span>No Answer Found in Channel Materials</span>
                      </div>
                      <p className={styles.insufficientText}>
                        {qaItem.answer ||
                          "The bot could not find sufficient evidence in this channel's completed files to answer this question. Please ensure relevant files have finished processing."}
                      </p>
                    </div>
                  )}

                  {/* S8-08: Answer with Citations */}
                  {qaItem.status === "success" && (
                    <>
                      <p className={styles.answerText}>{qaItem.answer}</p>

                      {qaItem.citations && qaItem.citations.length > 0 && (
                        <div className={styles.citationsContainer}>
                          <p className={styles.citationsHeading}>
                            <span aria-hidden="true">📄</span>
                            <span>Sources Cited:</span>
                          </p>
                          <ul className={styles.citationsList}>
                            {qaItem.citations.map((citation, idx) => {
                              const isDownloading =
                                downloadingFileId === citation.file_id;
                              return (
                                <li key={`${citation.file_id}-${citation.page}-${idx}`}>
                                  <button
                                    type="button"
                                    className={styles.citationButton}
                                    onClick={() =>
                                      void handleDownloadCitation(citation)
                                    }
                                    disabled={isDownloading}
                                    title={`Download ${citation.file_name} to view source document`}
                                  >
                                    <span
                                      className={styles.downloadIcon}
                                      aria-hidden="true"
                                    >
                                      {isDownloading ? "⏳" : "📥"}
                                    </span>
                                    <span>
                                      {isDownloading
                                        ? "Downloading..."
                                        : formatCitationLabel(citation)}
                                    </span>
                                  </button>
                                </li>
                              );
                            })}
                          </ul>
                        </div>
                      )}
                    </>
                  )}

                  {/* S8-10: Graceful Retryable Error State */}
                  {qaItem.status === "error" && (
                    <div className={styles.errorCard} role="alert">
                      <div className={styles.errorHeader}>
                        <span aria-hidden="true">⚠️</span>
                        <span>Unable to Generate Answer</span>
                      </div>
                      <p className={styles.errorText}>
                        {qaItem.errorMessage ||
                          "An error occurred while communicating with the bot."}
                      </p>
                      {qaItem.isRetryable && (
                        <button
                          type="button"
                          className={styles.retryButton}
                          onClick={() => handleRetry(qaItem)}
                          disabled={isLoading}
                        >
                          Retry question
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))
        )}
        <div ref={historyEndRef} />
      </div>

      {/* S8-07: Ask Input & Submit Form */}
      <form onSubmit={handleSubmit} className={styles.form}>
        <div className={styles.textareaWrapper}>
          <textarea
            className={styles.textarea}
            value={question}
            onChange={(e) => {
              setQuestion(e.target.value);
              if (validationError) setValidationError(null);
            }}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question about this channel's files (Press Enter to send, Shift+Enter for new line)..."
            disabled={isLoading}
            rows={2}
            maxLength={MAX_QUESTION_LENGTH}
            aria-label="Question for channel bot"
          />
        </div>

        <div className={styles.formFooter}>
          <div>
            {validationError ? (
              <p className={styles.validationError}>{validationError}</p>
            ) : (
              <span
                className={`${styles.charCount} ${
                  remainingChars < 100 ? styles.charCountExceeded : ""
                }`}
              >
                {question.length}/{MAX_QUESTION_LENGTH} characters
              </span>
            )}
          </div>

          <div className={styles.formActions}>
            <button
              type="submit"
              className={styles.submitButton}
              disabled={isLoading || question.trim().length === 0}
            >
              {isLoading ? "Searching..." : "Ask Bot"}
            </button>
          </div>
        </div>
      </form>
    </div>
  );
}
