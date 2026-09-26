import { ApiError } from "../../shared/api";
import type { ChannelMemberRole } from "./types";

export type WebSocketConnectionStatus =
  | "connecting"
  | "connected"
  | "disconnected"
  | "rejected";

/**
 * S8-12: Role-based visibility for chat and bot.
 * Per docs/security/permissions.md:
 * - View messages: Owner, Admin, Member, Read-only -> Yes
 * - Send messages: Owner, Admin, Member -> Yes; Read-only -> No
 * - Ask the bot: Owner, Admin, Member, Read-only -> Yes
 */
export function canViewChannelMessages(
  role: ChannelMemberRole | null | undefined,
): boolean {
  return (
    role === "owner" ||
    role === "admin" ||
    role === "member" ||
    role === "read_only"
  );
}

export function canSendChannelMessages(
  role: ChannelMemberRole | null | undefined,
): boolean {
  return role === "owner" || role === "admin" || role === "member";
}

export function canAskChannelBot(
  role: ChannelMemberRole | null | undefined,
): boolean {
  return (
    role === "owner" ||
    role === "admin" ||
    role === "member" ||
    role === "read_only"
  );
}

/**
 * S8-13: Error-state coverage for WebSocket connection rejection (S8-01).
 * Code 1008 indicates policy violation (token rejected, expired, or non-member).
 */
export function getWebSocketCloseErrorMessage(code?: number): string {
  if (code === 1008) {
    return "Real-time connection was rejected (unauthorized or session expired). Messages will be sent via HTTP fallback.";
  }
  return "Real-time connection was disconnected. Reconnecting... (HTTP fallback active)";
}

/**
 * S8-13: Error-state coverage for send-while-disconnected fallback (S8-05).
 */
export function getSendFallbackNotice(): string {
  return "Delivered via HTTP fallback (real-time socket disconnected).";
}

/**
 * Maps REST message sending errors to user-friendly messages.
 */
export function getChatMessageActionErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 403) {
      return "You do not have permission to send messages in this channel.";
    }
    if (error.status === 404) {
      return "Channel not found.";
    }
    if (error.status === 422) {
      return "Message content cannot be empty.";
    }
    return error.message || "Failed to send message.";
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return "Unable to send message. Please try again.";
}
