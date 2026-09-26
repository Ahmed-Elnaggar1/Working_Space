import { describe, expect, it } from "vitest";
import { ApiError } from "../../shared/api";
import {
  canAskChannelBot,
  canSendChannelMessages,
  canViewChannelMessages,
  getChatMessageActionErrorMessage,
  getSendFallbackNotice,
  getWebSocketCloseErrorMessage,
} from "./chatManagement";
import type { ChannelMemberRole } from "./types";

describe("S8-12: Role-based visibility for chat and bot", () => {
  it.each([
    ["owner", true, true, true],
    ["admin", true, true, true],
    ["member", true, true, true],
    ["read_only", true, true, false],
    [undefined, false, false, false],
  ] as const)(
    "role %s: canViewMessages=%s, canAskBot=%s, canSendMessages=%s",
    (role, expectedView, expectedAsk, expectedSend) => {
      const typedRole = role as ChannelMemberRole | undefined;
      expect(canViewChannelMessages(typedRole)).toBe(expectedView);
      expect(canAskChannelBot(typedRole)).toBe(expectedAsk);
      expect(canSendChannelMessages(typedRole)).toBe(expectedSend);
    },
  );

  it("confirms the exact combination for read_only: can view messages, can ask bot, but cannot send messages", () => {
    // Per permissions.md: "Ask the bot: Yes" for all roles, but "Send messages: No" for read_only
    const readOnlyRole: ChannelMemberRole = "read_only";
    expect(canViewChannelMessages(readOnlyRole)).toBe(true);
    expect(canAskChannelBot(readOnlyRole)).toBe(true);
    expect(canSendChannelMessages(readOnlyRole)).toBe(false);
  });
});

describe("S8-13: Error-state coverage", () => {
  it("returns verified, non-generic UI state for WebSocket connection rejection (code 1008)", () => {
    const rejectionMessage = getWebSocketCloseErrorMessage(1008);
    expect(rejectionMessage).toContain(
      "Real-time connection was rejected (unauthorized or session expired)",
    );
    expect(rejectionMessage).toContain("Messages will be sent via HTTP fallback");
  });

  it("returns verified, non-generic UI state for unexpected WebSocket disconnect", () => {
    const disconnectMessage = getWebSocketCloseErrorMessage(1006);
    expect(disconnectMessage).toContain(
      "Real-time connection was disconnected. Reconnecting...",
    );
    expect(disconnectMessage).toContain("HTTP fallback active");
  });

  it("returns verified, non-generic UI notice for send-while-disconnected fallback", () => {
    const notice = getSendFallbackNotice();
    expect(notice).toBe(
      "Delivered via HTTP fallback (real-time socket disconnected).",
    );
  });

  it("returns non-generic error messages for chat send HTTP errors", () => {
    expect(
      getChatMessageActionErrorMessage(
        new ApiError(403, "FORBIDDEN", "Forbidden"),
      ),
    ).toBe("You do not have permission to send messages in this channel.");

    expect(
      getChatMessageActionErrorMessage(
        new ApiError(404, "NOT_FOUND", "Channel not found"),
      ),
    ).toBe("Channel not found.");

    expect(
      getChatMessageActionErrorMessage(
        new ApiError(422, "UNPROCESSABLE_ENTITY", "Validation error"),
      ),
    ).toBe("Message content cannot be empty.");

    expect(
      getChatMessageActionErrorMessage(
        new ApiError(500, "SERVER_ERROR", "Server error"),
      ),
    ).toBe("Server error");

    expect(getChatMessageActionErrorMessage(new Error("Network failed"))).toBe(
      "Network failed",
    );
  });
});
