import {
    apiClient,
    getBaseUrl,
    getTokenProvider
} from "../../shared/api"

import type {
    markAllReadResponse,
    notificationItem,
    notificationPage,
    unreadCountResponse,
} from "./types"

export async function getNotifications(params?: {
    limit?: number;
    before?: string;
    isRead?: boolean;
}): Promise<notificationPage> {
    return apiClient<notificationPage>(
        "/notifications", {
        method: "GET",
        params: {
            limit: params?.limit ?? 50,
            before: params?.before,
        },
    }
    );
}
export async function getUnreadCount(): Promise<unreadCountResponse> {
    return apiClient<unreadCountResponse>("/notifications/unread-count", {
        method: "GET",
    });
}
export async function markNotificationRead(
    notificationId: string
): Promise<notificationItem> {
    return apiClient<notificationItem>(`/notifications/${notificationId}/read`, {
        method: "PATCH",
    });
}

export async function markAllNotificationsRead(): Promise<markAllReadResponse> {
    return apiClient<markAllReadResponse>("/notifications/read-all", {
        method: "PATCH",
    });
}

export function getNotificationWebSocketUrl(): string {
    const baseUrl = getBaseUrl();
    const wsProtocol = baseUrl.startsWith("https") ? "wss" : "ws";
    const host = baseUrl.replace(/^https?:\/\//, "");
    const tokenProvider = getTokenProvider();
    const token = tokenProvider ? tokenProvider() : null;
    return `${wsProtocol}://${host}/ws/notifications${token ? `?token=${encodeURIComponent(token)}` : ""}`;
}