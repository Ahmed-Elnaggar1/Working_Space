import { useNotifications } from "../useNotifications";
import styles from "./NotificationBell.module.css";

export function NotificationBell() {
  const { unreadCount, isOpen, toggleOpen } = useNotifications();

  return (
    <button
      type="button"
      className={`${styles.bellButton} ${isOpen ? styles.active : ""}`}
      onClick={toggleOpen}
      aria-label={`Notifications ${unreadCount > 0 ? `(${unreadCount} unread)` : ""}`}
      aria-expanded={isOpen}
      aria-haspopup="dialog"
      title={unreadCount > 0 ? `${unreadCount} unread notifications` : "Notifications"}
    >
      <svg
        className={styles.bellIcon}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </svg>
      {unreadCount > 0 && (
        <span className={styles.badge}>
          {unreadCount > 99 ? "99+" : unreadCount}
        </span>
      )}
    </button>
  );
}
