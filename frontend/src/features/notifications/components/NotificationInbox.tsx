import { useMemo, useState, type MouseEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useNotifications } from "../useNotifications";
import type { notificationItem, notificationType } from "../types";
import { formatRelativeTime } from "../utils";
import styles from "./NotificationInbox.module.css";

interface NotificationInboxProps {
  onSelectChannel?: (channelId: string) => void;
}

export function NotificationInbox({ onSelectChannel }: NotificationInboxProps) {
  const navigate = useNavigate();
  const {
    notifications,
    unreadCount,
    isLoading,
    hasMore,
    isOpen,
    setIsOpen,
    loadMore,
    markAsRead,
    markAllAsRead,
  } = useNotifications();

  const [activeTab, setActiveTab] = useState<"all" | notificationType>("all");

  const filteredNotifications = useMemo(() => {
    if (activeTab === "all") return notifications;
    return notifications.filter((n) => n.type === activeTab);
  }, [notifications, activeTab]);

  if (!isOpen) return null;

  function handleItemClick(item: notificationItem) {
    if (!item.is_read) {
      void markAsRead(item.id);
    }
    setIsOpen(false);
    if (onSelectChannel) {
      onSelectChannel(item.channel_id);
    } else {
      navigate(`/channels/${item.channel_id}`);
    }
  }

  function handleMarkSingle(e: MouseEvent, id: string) {
    e.stopPropagation();
    void markAsRead(id);
  }

  return (
    <>
      <div
        className={styles.inboxBackdrop}
        onClick={() => setIsOpen(false)}
        aria-hidden="true"
      />
      <section
        className={styles.inboxContainer}
        role="dialog"
        aria-label="Notifications Inbox"
      >
        {/* Header */}
        <header className={styles.header}>
          <div className={styles.headerLeft}>
            <h2 className={styles.title}>Notifications</h2>
            {unreadCount > 0 && (
              <span className={styles.unreadChip}>{unreadCount} new</span>
            )}
          </div>
          <div className={styles.headerRight}>
            <button
              type="button"
              className={styles.markAllBtn}
              onClick={() => void markAllAsRead()}
              disabled={unreadCount === 0}
              title="Mark all notifications as read"
            >
              Mark all as read
            </button>
            <button
              type="button"
              className={styles.closeBtn}
              onClick={() => setIsOpen(false)}
              aria-label="Close notifications"
            >
              ×
            </button>
          </div>
        </header>

        {/* Filter Tabs */}
        <nav className={styles.tabs} aria-label="Notification filters">
          <button
            type="button"
            className={`${styles.tab} ${activeTab === "all" ? styles.activeTab : ""}`}
            onClick={() => setActiveTab("all")}
          >
            All
          </button>
          <button
            type="button"
            className={`${styles.tab} ${activeTab === "mention" ? styles.activeTab : ""}`}
            onClick={() => setActiveTab("mention")}
          >
            Mentions (@)
          </button>
          <button
            type="button"
            className={`${styles.tab} ${activeTab === "thread_reply" ? styles.activeTab : ""}`}
            onClick={() => setActiveTab("thread_reply")}
          >
            Replies (💬)
          </button>
        </nav>

        {/* List */}
        <div className={styles.list}>
          {filteredNotifications.length === 0 ? (
            <div className={styles.emptyState}>
              <span className={styles.emptyIcon}>✨</span>
              <p className={styles.emptyTitle}>You're all caught up</p>
              <p className={styles.emptyText}>
                {activeTab === "all"
                  ? "No notifications yet."
                  : `No ${activeTab === "mention" ? "mentions" : "thread replies"} right now.`}
              </p>
            </div>
          ) : (
            filteredNotifications.map((item) => {
              const isMention = item.type === "mention";
              return (
                <button
                  key={item.id}
                  type="button"
                  className={`${styles.item} ${!item.is_read ? styles.unread : ""}`}
                  onClick={() => handleItemClick(item)}
                >
                  <div
                    className={`${styles.typeIcon} ${
                      isMention ? styles.typeMention : styles.typeThread
                    }`}
                  >
                    {isMention ? "@" : "💬"}
                  </div>

                  <div className={styles.itemContent}>
                    <p className={styles.itemTitle}>
                      {isMention
                        ? "Mentioned you in a message"
                        : "New reply in your thread"}
                    </p>
                    <div className={styles.itemMeta}>
                      <span className={styles.time}>
                        {formatRelativeTime(item.created_at)}
                      </span>
                    </div>
                  </div>

                  <div className={styles.itemActions}>
                    {!item.is_read && <span className={styles.unreadDot} />}
                    {!item.is_read && (
                      <button
                        type="button"
                        className={styles.markReadBtn}
                        onClick={(e) => handleMarkSingle(e, item.id)}
                        title="Mark as read"
                        aria-label="Mark as read"
                      >
                        ✓
                      </button>
                    )}
                  </div>
                </button>
              );
            })
          )}
        </div>

        {/* Load more */}
        {hasMore && (
          <div className={styles.loadMoreWrapper}>
            <button
              type="button"
              className={styles.loadMoreBtn}
              onClick={() => void loadMore()}
              disabled={isLoading}
            >
              {isLoading ? "Loading..." : "Load older notifications"}
            </button>
          </div>
        )}
      </section>
    </>
  );
}
