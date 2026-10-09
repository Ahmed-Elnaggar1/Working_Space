export type notificationType = "mention" | "thread_reply";

export interface notificationItem {
    id: string;
    user_id: string;
    actor_id: string;
    channel_id: string;
    message_id: string;
    type: notificationType;
    is_read: boolean;
    created_at: string;
}

export interface notificationPage {
    items: notificationItem[];
    next_cursor: string | null;
}

export interface unreadCountResponse {
    unread_count: number;
}


export interface markAllReadResponse {
    marked_read_count: number;
}