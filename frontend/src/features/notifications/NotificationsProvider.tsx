import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useAuth } from "../auth/useAuth";
import {
  getNotifications,
  getNotificationWebSocketUrl,
  getUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
} from "./api";
import { NotificationsContext } from "./context";
import type { notificationItem } from "./types";

export function NotificationsProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [notifications, setNotifications] = useState<notificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState<boolean>(false);

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const toggleOpen = useCallback(() => {
    setIsOpen((prev) => !prev);
  }, []);

  // 1. Initial fetch of unread count and first page
  useEffect(() => {
    let isMounted = true;

    async function fetchInitial() {
      if (!user) return;
      try {
        const [countRes, notifRes] = await Promise.all([
          getUnreadCount(),
          getNotifications({ limit: 20 }),
        ]);
        if (!isMounted) return;
        setUnreadCount(countRes.unread_count);
        setNotifications(notifRes.items);
        setNextCursor(notifRes.next_cursor);
      } catch {
        if (!isMounted) return;
        setError("Failed to load notifications.");
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    void fetchInitial();

    return () => {
      isMounted = false;
    };
  }, [user]);

  // 2. Real-time WebSocket connection
  useEffect(() => {
    if (!user) {
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      return;
    }

    let isMounted = true;

    function connect() {
      if (!isMounted) return;
      const wsUrl = getNotificationWebSocketUrl();
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const newNotif = JSON.parse(event.data) as notificationItem;
          if (newNotif && newNotif.id) {
            setNotifications((prev) => [newNotif, ...prev]);
            setUnreadCount((prev) => prev + 1);
          }
        } catch {
          // ignore non-json messages
        }
      };

      ws.onclose = () => {
        if (!isMounted) return;
        // Auto-reconnect after 3 seconds
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 3000);
      };
    }

    connect();

    return () => {
      isMounted = false;
      if (reconnectTimeoutRef.current) {
        window.clearTimeout(reconnectTimeoutRef.current);
      }
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [user]);

  // 3. Pagination: load older notifications
  const loadMore = useCallback(async () => {
    if (!nextCursor || isLoading) return;
    setIsLoading(true);
    try {
      const res = await getNotifications({ limit: 20, before: nextCursor });
      setNotifications((prev) => [...prev, ...res.items]);
      setNextCursor(res.next_cursor);
    } catch {
      setError("Failed to load more notifications.");
    } finally {
      setIsLoading(false);
    }
  }, [nextCursor, isLoading]);

  // 4. Mark single notification as read (with optimistic UI update)
  const markAsRead = useCallback(async (id: string) => {
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
    );
    setUnreadCount((prev) => Math.max(0, prev - 1));

    try {
      await markNotificationRead(id);
    } catch {
      // Refresh on failure
      void getUnreadCount().then((res) => setUnreadCount(res.unread_count));
    }
  }, []);

  // 5. Mark all as read (with optimistic UI update)
  const markAllAsRead = useCallback(async () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
    setUnreadCount(0);

    try {
      await markAllNotificationsRead();
    } catch {
      void getUnreadCount().then((res) => setUnreadCount(res.unread_count));
    }
  }, []);

  return (
    <NotificationsContext.Provider
      value={{
        notifications,
        unreadCount,
        isLoading,
        error,
        hasMore: Boolean(nextCursor),
        isOpen,
        setIsOpen,
        toggleOpen,
        loadMore,
        markAsRead,
        markAllAsRead,
      }}
    >
      {children}
    </NotificationsContext.Provider>
  );
}
