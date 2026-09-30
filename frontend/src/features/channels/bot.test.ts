import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { ApiError } from "../../shared/api";
import {
  clearSessionAskHistory,
  formatCitationLabel,
  getBotActionErrorMessage,
  getSessionStorageKey,
  isRetryableBotError,
  loadSessionAskHistory,
  MAX_QUESTION_LENGTH,
  saveSessionAskHistory,
  validateQuestion,
} from "./bot";
import type { BotCitation, BotQAPair } from "./types";

describe("Bot domain logic and validation", () => {
  describe("validateQuestion", () => {
    it("rejects an empty question", () => {
      const result = validateQuestion("");
      expect(result.valid).toBe(false);
      expect(result.error).toMatch(/please enter a question/i);
    });

    it("rejects a whitespace-only question", () => {
      const result = validateQuestion("   \n\t  ");
      expect(result.valid).toBe(false);
      expect(result.error).toMatch(/please enter a question/i);
    });

    it("accepts a normal question", () => {
      const result = validateQuestion("What is the project release schedule?");
      expect(result.valid).toBe(true);
      expect(result.error).toBeUndefined();
    });

    it("rejects questions longer than MAX_QUESTION_LENGTH", () => {
      const longQuestion = "a".repeat(MAX_QUESTION_LENGTH + 1);
      const result = validateQuestion(longQuestion);
      expect(result.valid).toBe(false);
      expect(result.error).toContain(`cannot exceed ${MAX_QUESTION_LENGTH}`);
    });
  });

  describe("formatCitationLabel", () => {
    it("formats citations with a page number", () => {
      const citation: BotCitation = {
        file_id: "file-1",
        file_name: "roadmap.pdf",
        page: 4,
      };
      expect(formatCitationLabel(citation)).toBe("roadmap.pdf (Page 4)");
    });

    it("formats citations with page 0 correctly", () => {
      const citation: BotCitation = {
        file_id: "file-1",
        file_name: "cover.pdf",
        page: 0,
      };
      expect(formatCitationLabel(citation)).toBe("cover.pdf (Page 0)");
    });

    it("formats citations without a page number", () => {
      const citation: BotCitation = {
        file_id: "file-2",
        file_name: "notes.txt",
        page: null,
      };
      expect(formatCitationLabel(citation)).toBe("notes.txt");
    });
  });

  describe("getBotActionErrorMessage", () => {
    it("handles 504 GATEWAY_TIMEOUT with clear retry guidance", () => {
      const error = new ApiError(504, "GATEWAY_TIMEOUT", "Gateway Timeout");
      const message = getBotActionErrorMessage(error);
      expect(message).toContain("timed out");
      expect(message).toContain("retry");
    });

    it("handles 502 BAD_GATEWAY with clear AI service error guidance", () => {
      const error = new ApiError(
        502,
        "BAD_GATEWAY",
        "LLM service temporarily unavailable",
      );
      const message = getBotActionErrorMessage(error);
      expect(message).toContain("LLM service temporarily unavailable");
    });

    it("handles 403 Forbidden with permission error", () => {
      const error = new ApiError(403, "FORBIDDEN", "Forbidden");
      expect(getBotActionErrorMessage(error)).toContain("permission");
    });

    it("handles 404 Not Found", () => {
      const error = new ApiError(404, "NOT_FOUND", "Not found");
      expect(getBotActionErrorMessage(error)).toContain("Channel not found");
    });

    it("handles 422 Validation Error", () => {
      const error = new ApiError(422, "VALIDATION_ERROR", "Validation failed");
      expect(getBotActionErrorMessage(error)).toContain("Invalid question payload");
    });

    it("handles generic Error instances", () => {
      const error = new Error("Network connection dropped");
      expect(getBotActionErrorMessage(error)).toBe("Network connection dropped");
    });

    it("falls back to default message for unknown error types", () => {
      expect(getBotActionErrorMessage("some weird failure")).toContain(
        "unexpected error occurred",
      );
    });
  });

  describe("isRetryableBotError", () => {
    it("marks 502 and 504 errors as retryable", () => {
      expect(isRetryableBotError(new ApiError(502, "BAD_GATEWAY", "err"))).toBe(
        true,
      );
      expect(
        isRetryableBotError(new ApiError(504, "GATEWAY_TIMEOUT", "err")),
      ).toBe(true);
    });

    it("marks 500 internal errors and generic network errors as retryable", () => {
      expect(
        isRetryableBotError(new ApiError(500, "INTERNAL_ERROR", "err")),
      ).toBe(true);
      expect(isRetryableBotError(new Error("NetworkError"))).toBe(true);
    });

    it("does not mark 401, 403, 422 as retryable", () => {
      expect(isRetryableBotError(new ApiError(401, "UNAUTHORIZED", "err"))).toBe(
        false,
      );
      expect(isRetryableBotError(new ApiError(403, "FORBIDDEN", "err"))).toBe(
        false,
      );
      expect(
        isRetryableBotError(new ApiError(422, "VALIDATION_ERROR", "err")),
      ).toBe(false);
    });
  });

  describe("session-local ask history helpers", () => {
    const channelId = "test-channel-123";
    let mockStore: Map<string, string>;

    beforeEach(() => {
      mockStore = new Map<string, string>();
      const mockStorage = {
        getItem: (key: string) => mockStore.get(key) ?? null,
        setItem: (key: string, val: string) => mockStore.set(key, String(val)),
        removeItem: (key: string) => mockStore.delete(key),
        clear: () => mockStore.clear(),
        length: 0,
        key: () => null,
      };
      (globalThis as unknown as { window?: { sessionStorage?: typeof mockStorage }; sessionStorage?: typeof mockStorage }).window = {
        sessionStorage: mockStorage,
      };
      (globalThis as unknown as { sessionStorage?: typeof mockStorage }).sessionStorage = mockStorage;
    });

    afterEach(() => {
      mockStore.clear();
    });

    it("returns empty array when no history exists", () => {
      expect(loadSessionAskHistory(channelId)).toEqual([]);
    });

    it("saves and loads history round-trip", () => {
      const history: BotQAPair[] = [
        {
          id: "qa-1",
          question: "What is this file?",
          answer: "It is a specification document.",
          citations: [
            {
              file_id: "file-1",
              file_name: "spec.pdf",
              page: 1,
            },
          ],
          insufficient_evidence: false,
          status: "success",
          createdAt: new Date().toISOString(),
        },
      ];

      saveSessionAskHistory(channelId, history);
      const loaded = loadSessionAskHistory(channelId);
      expect(loaded).toEqual(history);
    });

    it("clears history for a specific channel", () => {
      const history: BotQAPair[] = [
        {
          id: "qa-1",
          question: "Test question",
          status: "insufficient_evidence",
          insufficient_evidence: true,
          createdAt: new Date().toISOString(),
        },
      ];

      saveSessionAskHistory(channelId, history);
      expect(loadSessionAskHistory(channelId).length).toBe(1);

      clearSessionAskHistory(channelId);
      expect(loadSessionAskHistory(channelId)).toEqual([]);
    });

    it("handles corrupted sessionStorage JSON gracefully", () => {
      globalThis.sessionStorage.setItem(
        getSessionStorageKey(channelId),
        "invalid-json{{{",
      );
      expect(loadSessionAskHistory(channelId)).toEqual([]);
    });

    it("handles non-array sessionStorage JSON gracefully", () => {
      globalThis.sessionStorage.setItem(
        getSessionStorageKey(channelId),
        JSON.stringify({ notAnArray: true }),
      );
      expect(loadSessionAskHistory(channelId)).toEqual([]);
    });
  });
});
