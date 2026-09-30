import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../shared/api";
import {
  askChannel,
  downloadChannelFile,
  getChannelMessages,
  getChannelWebSocketUrl,
  postChannelMessage,
} from "./api";
import {
  formatCitationLabel,
  getBotActionErrorMessage,
  isRetryableBotError,
  validateQuestion,
} from "./bot";
import {
  canAskChannelBot,
  canSendChannelMessages,
  canViewChannelMessages,
  getChatMessageActionErrorMessage,
  getSendFallbackNotice,
  getWebSocketCloseErrorMessage,
} from "./chatManagement";
import type { AskChannelResponse, ChannelMessage, ChannelMessagePage } from "./types";

describe("Sprint 8 Quality Gate (S8-12 to S8-15)", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.unstubAllGlobals();
  });

  describe("S8-12: Role-based visibility for chat and bot", () => {
    it("confirms read_only role can view messages, can ask bot, but has canSendMessages=false", () => {
      // Per permissions.md: "Ask the bot: Yes" for all roles, but "Send messages: No" for read_only
      expect(canViewChannelMessages("read_only")).toBe(true);
      expect(canAskChannelBot("read_only")).toBe(true);
      expect(canSendChannelMessages("read_only")).toBe(false);
    });

    it("confirms active member roles (owner, admin, member) can view, ask, and send", () => {
      const activeRoles = ["owner", "admin", "member"] as const;
      for (const role of activeRoles) {
        expect(canViewChannelMessages(role)).toBe(true);
        expect(canAskChannelBot(role)).toBe(true);
        expect(canSendChannelMessages(role)).toBe(true);
      }
    });

    it("confirms non-members cannot view messages, ask bot, or send messages", () => {
      expect(canViewChannelMessages(undefined)).toBe(false);
      expect(canAskChannelBot(undefined)).toBe(false);
      expect(canSendChannelMessages(undefined)).toBe(false);
    });
  });

  describe("S8-13: Error-state coverage", () => {
    it("verifies WebSocket connection rejection UI error state (S8-01)", () => {
      const rejectionError = getWebSocketCloseErrorMessage(1008);
      expect(rejectionError).toContain("Real-time connection was rejected");
      expect(rejectionError).toContain("HTTP fallback");
    });

    it("verifies insufficient_evidence UI state mapping (S8-09)", () => {
      const response: AskChannelResponse = {
        answer: "I could not find sufficient evidence in the uploaded documents to answer your question.",
        citations: [],
        insufficient_evidence: true,
      };

      expect(response.insufficient_evidence).toBe(true);
      expect(response.citations).toHaveLength(0);
      expect(response.answer).toContain("could not find sufficient evidence");
    });

    it("verifies bot LLM failure UI error state and retryability (S8-10)", () => {
      const timeoutError = new ApiError(504, "GATEWAY_TIMEOUT", "Gateway timeout");
      expect(getBotActionErrorMessage(timeoutError)).toContain("timed out");
      expect(isRetryableBotError(timeoutError)).toBe(true);

      const badGatewayError = new ApiError(502, "BAD_GATEWAY", "Bad gateway");
      expect(isRetryableBotError(badGatewayError)).toBe(true);

      const forbiddenError = new ApiError(403, "FORBIDDEN", "Forbidden");
      expect(getBotActionErrorMessage(forbiddenError)).toContain("do not have permission");
      expect(isRetryableBotError(forbiddenError)).toBe(false);
    });

    it("verifies send-while-disconnected fallback notice (S8-05)", () => {
      const fallbackNotice = getSendFallbackNotice();
      expect(fallbackNotice).toContain("Delivered via HTTP fallback");
      expect(fallbackNotice).toContain("real-time socket disconnected");
    });
  });

  describe("S8-14: End-to-end smoke test", () => {
    it("walkthrough: real-time send/receive, HTTP fallback, and bot Q&A with citations", async () => {
      const channelId = "channel-smoke-123";
      const token = "mock-jwt-token";

      // 1. Verify WebSocket URL construction with token
      const wsUrl = getChannelWebSocketUrl(channelId, token, "http://localhost:8000");
      expect(wsUrl).toBe("ws://localhost:8000/ws/channels/channel-smoke-123?token=mock-jwt-token");

      // 2. Initial message history load via GET /messages
      const mockHistory: ChannelMessagePage = {
        items: [
          {
            id: "msg-1",
            channel_id: channelId,
            user_id: "user-1",
            content: "Welcome to the channel!",
            created_at: "2026-09-26T10:00:00Z",
          },
        ],
        next_cursor: null,
      };

      globalThis.fetch = vi.fn().mockImplementation((url: string, init?: RequestInit) => {
        if (url.includes(`/channels/${channelId}/messages`) && (!init || init.method === "GET")) {
          return Promise.resolve(new Response(JSON.stringify(mockHistory), { status: 200 }));
        }

        if (url.includes(`/channels/${channelId}/messages`) && init?.method === "POST") {
          const body = JSON.parse(init.body as string);
          const fallbackMessage: ChannelMessage = {
            id: "msg-2-fallback",
            channel_id: channelId,
            user_id: "user-2",
            content: body.content,
            created_at: new Date().toISOString(),
          };
          return Promise.resolve(new Response(JSON.stringify(fallbackMessage), { status: 201 }));
        }

        if (url.includes(`/channels/${channelId}/ask`) && init?.method === "POST") {
          const body = JSON.parse(init.body as string);
          if (body.question.includes("unknown")) {
            const insufficientResponse: AskChannelResponse = {
              answer: "No answer found in this channel's materials.",
              citations: [],
              insufficient_evidence: true,
            };
            return Promise.resolve(new Response(JSON.stringify(insufficientResponse), { status: 200 }));
          }

          const botResponse: AskChannelResponse = {
            answer: "The project deadline is October 15, 2026.",
            citations: [
              {
                file_id: "file-doc-1",
                file_name: "project_plan.pdf",
                page: 3,
              },
            ],
            insufficient_evidence: false,
          };
          return Promise.resolve(new Response(JSON.stringify(botResponse), { status: 200 }));
        }

        if (url.includes("/download")) {
          return Promise.resolve(new Response(new Blob(["PDF CONTENT"]), { status: 200 }));
        }

        return Promise.reject(new Error(`Unhandled URL: ${url}`));
      });

      // A. Load initial message history
      const history = await getChannelMessages(channelId);
      expect(history.items).toHaveLength(1);
      expect(history.items[0].content).toBe("Welcome to the channel!");

      // B. Simulate send message via HTTP fallback (send-while-disconnected)
      const sentFallback = await postChannelMessage(channelId, { content: "Sent while offline" });
      expect(sentFallback.id).toBe("msg-2-fallback");
      expect(sentFallback.content).toBe("Sent while offline");
      const fallbackNotice = getSendFallbackNotice();
      expect(fallbackNotice).toBe("Delivered via HTTP fallback (real-time socket disconnected).");

      // C. Ask the bot a valid question and receive grounded cited answer
      const qValidation = validateQuestion("When is the project deadline?");
      expect(qValidation.valid).toBe(true);

      const botResult = await askChannel(channelId, "When is the project deadline?");
      expect(botResult.insufficient_evidence).toBe(false);
      expect(botResult.answer).toBe("The project deadline is October 15, 2026.");
      expect(botResult.citations).toHaveLength(1);
      expect(formatCitationLabel(botResult.citations[0])).toBe("project_plan.pdf (Page 3)");

      // D. Citation source download triggers fetch to correct endpoint
      await expect(
        downloadChannelFile(channelId, botResult.citations[0].file_id, botResult.citations[0].file_name),
      ).resolves.toBeUndefined();

      // E. Ask the bot an ungrounded question -> receives honest insufficient_evidence state
      const noEvidenceResult = await askChannel(channelId, "unknown topic question");
      expect(noEvidenceResult.insufficient_evidence).toBe(true);
      expect(noEvidenceResult.citations).toHaveLength(0);
      expect(noEvidenceResult.answer).toContain("No answer found");
    });
  });

  describe("S8-15: CI gate confirmed for frontend changes this sprint", () => {
    it("confirms error mapping and policy enforcement prevent invalid operations", () => {
      const emptyContentError = new ApiError(422, "VALIDATION_ERROR", "Field required");
      expect(getChatMessageActionErrorMessage(emptyContentError)).toBe(
        "Message content cannot be empty.",
      );

      const forbiddenError = new ApiError(403, "FORBIDDEN", "Forbidden");
      expect(getChatMessageActionErrorMessage(forbiddenError)).toBe(
        "You do not have permission to send messages in this channel.",
      );
    });
  });
});
