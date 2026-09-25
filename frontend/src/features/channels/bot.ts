import { ApiError } from "../../shared/api";
import type { BotCitation, BotQAPair } from "./types";

export const MAX_QUESTION_LENGTH = 4000;
export const LONG_WAIT_THRESHOLD_MS = 3500;
export const BOT_SESSION_HISTORY_PREFIX = "vault_bot_history_";

export function validateQuestion(question: string): {
  valid: boolean;
  error?: string;
} {
  const trimmed = question.trim();
  if (trimmed.length === 0) {
    return { valid: false, error: "Please enter a question to ask the bot." };
  }
  if (trimmed.length > MAX_QUESTION_LENGTH) {
    return {
      valid: false,
      error: `Question cannot exceed ${MAX_QUESTION_LENGTH} characters (currently ${trimmed.length}).`,
    };
  }
  return { valid: true };
}

export function formatCitationLabel(citation: BotCitation): string {
  if (citation.page !== null && citation.page !== undefined) {
    return `${citation.file_name} (Page ${citation.page})`;
  }
  return citation.file_name;
}

export function isRetryableBotError(error: unknown): boolean {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403 || error.status === 422) {
      return false;
    }
    return true;
  }
  return true;
}

export function getBotActionErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 504 || error.code === "GATEWAY_TIMEOUT") {
      return "The AI model request timed out while generating an answer. Please retry your question.";
    }
    if (error.status === 502 || error.code === "BAD_GATEWAY") {
      return (
        error.message ||
        "The AI service encountered an error or was temporarily unavailable. Please retry your question."
      );
    }
    if (error.status === 403) {
      return "You do not have permission to ask questions in this channel.";
    }
    if (error.status === 404) {
      return "Channel not found.";
    }
    if (error.status === 422) {
      return "Invalid question payload. Please adjust your question and try again.";
    }
    return (
      error.message ||
      `Request failed with status ${error.status}. Please try again.`
    );
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return "An unexpected error occurred while communicating with the bot. Please try again.";
}

export function getSessionStorageKey(channelId: string): string {
  return `${BOT_SESSION_HISTORY_PREFIX}${channelId}`;
}

export function loadSessionAskHistory(channelId: string): BotQAPair[] {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return [];
  }
  try {
    const raw = window.sessionStorage.getItem(getSessionStorageKey(channelId));
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed;
  } catch {
    return [];
  }
}

export function saveSessionAskHistory(
  channelId: string,
  history: BotQAPair[],
): void {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return;
  }
  try {
    window.sessionStorage.setItem(
      getSessionStorageKey(channelId),
      JSON.stringify(history),
    );
  } catch {
    // Silently ignore quota or storage exceptions
  }
}

export function clearSessionAskHistory(channelId: string): void {
  if (typeof window === "undefined" || !window.sessionStorage) {
    return;
  }
  try {
    window.sessionStorage.removeItem(getSessionStorageKey(channelId));
  } catch {
    // Silently ignore
  }
}
