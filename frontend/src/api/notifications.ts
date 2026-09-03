import { apiClient } from "@/api/client";
import type { NotificationEvent } from "@/types/teacherReview";

/** Storage-only notification framework (Module 07, Feature 10, ADR-046).
 * See `backend/app/api/v1/endpoints/notifications.py`. */
export async function listMyNotifications(unreadOnly = false): Promise<NotificationEvent[]> {
  const { data } = await apiClient.get<NotificationEvent[]>("/notifications", {
    params: unreadOnly ? { unread_only: true } : undefined,
  });
  return data;
}

export async function getUnreadNotificationCount(): Promise<number> {
  const { data } = await apiClient.get<{ unread_count: number }>("/notifications/unread-count");
  return data.unread_count;
}

export async function markNotificationRead(id: string): Promise<NotificationEvent> {
  const { data } = await apiClient.post<NotificationEvent>(`/notifications/${id}/read`);
  return data;
}
