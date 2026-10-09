import { createContext } from "react";
import type { notificationItem } from "./types";

export interface NotificationsContextValue {
  notifications: notificationItem[];
  unreadCount: number;
  isLoading: boolean;
  error: string | null;
  hasMore: boolean;
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  toggleOpen: () => void;
  loadMore: () => Promise<void>;
  markAsRead: (id: string) => Promise<void>;
  markAllAsRead: () => Promise<void>;
}

export const NotificationsContext =
  createContext<NotificationsContextValue | null>(null);
