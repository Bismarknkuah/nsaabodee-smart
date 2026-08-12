import { authFetch } from "./authFetch";
import { unwrapPaginated } from "./unwrapPaginated";

export interface NotificationEntry {
  id: string;
  category: string;
  message: string;
  recipient_role: string;
  related_member: string | null;
  related_member_name: string | null;
  is_read: boolean;
  created_at: string;
}

export interface DeliveryAttemptEntry {
  id: string;
  notification: string;
  channel: "console" | "email" | "sms" | "whatsapp";
  recipient_address: string;
  status: "sent" | "skipped_not_configured" | "skipped_no_address" | "failed";
  provider_response: string;
  attempted_at: string;
}

async function request<T>(path: string): Promise<T> {
  const res = await authFetch(path);
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  const json = await res.json();
  return unwrapPaginated<T>(json) as T;
}

export const notificationsApi = {
  list: () => request<NotificationEntry[]>(`/notifications/`),
  deliveryAttempts: (notificationId: string) =>
    request<DeliveryAttemptEntry[]>(`/delivery-attempts/?notification=${notificationId}`),
};
