import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  getNotifications,
  getNotificationWebSocketUrl,
  getUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
} from "./api";
import { setTokenProvider } from "../../shared/api";
import { formatRelativeTime } from "./utils";

describe("notifications API and utilities", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    setTokenProvider(null);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  describe("API Client", () => {
    it("fetches notifications with default pagination limit", async () => {
      const mockData = {
        items: [
          {
            id: "notif-1",
            user_id: "user-1",
            actor_id: "actor-1",
            channel_id: "channel-1",
            message_id: "msg-1",
            type: "mention",
            is_read: false,
            created_at: new Date().toISOString(),
          },
        ],
        next_cursor: "cursor-123",
      };

      globalThis.fetch = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(mockData), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );

      const res = await getNotifications();
      expect(res).toEqual(mockData);

      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/notifications?limit=50"),
        expect.objectContaining({ method: "GET" })
      );
    });

    it("appends cursor parameter when before is provided", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ items: [], next_cursor: null }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );

      await getNotifications({ limit: 10, before: "abc-cursor" });

      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/notifications?limit=10&before=abc-cursor"),
        expect.objectContaining({ method: "GET" })
      );
    });

    it("fetches unread count", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ unread_count: 5 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );

      const res = await getUnreadCount();
      expect(res.unread_count).toBe(5);

      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/notifications/unread-count"),
        expect.objectContaining({ method: "GET" })
      );
    });

    it("marks single notification as read", async () => {
      const mockItem = {
        id: "notif-42",
        user_id: "user-1",
        actor_id: "actor-2",
        channel_id: "ch-1",
        message_id: "msg-9",
        type: "thread_reply",
        is_read: true,
        created_at: new Date().toISOString(),
      };

      globalThis.fetch = vi.fn().mockResolvedValue(
        new Response(JSON.stringify(mockItem), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );

      const res = await markNotificationRead("notif-42");
      expect(res.is_read).toBe(true);

      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/notifications/notif-42/read"),
        expect.objectContaining({ method: "PATCH" })
      );
    });

    it("marks all notifications as read", async () => {
      globalThis.fetch = vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ marked_read_count: 3 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        })
      );

      const res = await markAllNotificationsRead();
      expect(res.marked_read_count).toBe(3);

      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/notifications/read-all"),
        expect.objectContaining({ method: "PATCH" })
      );
    });

    it("generates correct authenticated WebSocket URL", () => {
      setTokenProvider(() => "secret-token-xyz");
      const url = getNotificationWebSocketUrl();

      expect(url).toContain("/ws/notifications?token=secret-token-xyz");
      expect(url.startsWith("ws://") || url.startsWith("wss://")).toBe(true);
    });

    it("generates WebSocket URL without token when unauthenticated", () => {
      setTokenProvider(null);
      const url = getNotificationWebSocketUrl();

      expect(url).toContain("/ws/notifications");
      expect(url).not.toContain("?token=");
    });
  });

  describe("formatRelativeTime utility", () => {
    it("returns 'Just now' for timestamps less than 60 seconds ago", () => {
      const now = new Date();
      expect(formatRelativeTime(now.toISOString())).toBe("Just now");
    });

    it("returns minutes ago for timestamps under an hour", () => {
      const date = new Date(Date.now() - 15 * 60 * 1000); // 15 mins ago
      expect(formatRelativeTime(date.toISOString())).toBe("15m ago");
    });

    it("returns hours ago for timestamps under 24 hours", () => {
      const date = new Date(Date.now() - 4 * 60 * 60 * 1000); // 4 hours ago
      expect(formatRelativeTime(date.toISOString())).toBe("4h ago");
    });

    it("returns days ago for timestamps under 7 days", () => {
      const date = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000); // 3 days ago
      expect(formatRelativeTime(date.toISOString())).toBe("3d ago");
    });
  });
});
