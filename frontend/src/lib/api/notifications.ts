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
  /** "Community members should have option where they can set or sort the notifications." All three filters are optional and combinable. */
  list: (filters?: { category?: string; is_read?: boolean; ordering?: "oldest" | "newest" }) => {
    const params = new URLSearchParams();
    if (filters?.category) params.set("category", filters.category);
    if (filters?.is_read !== undefined) params.set("is_read", String(filters.is_read));
    if (filters?.ordering) params.set("ordering", filters.ordering);
    const query = params.toString();
    return request<NotificationEntry[]>(`/notifications/${query ? `?${query}` : ""}`);
  },
  deliveryAttempts: (notificationId: string) =>
    request<DeliveryAttemptEntry[]>(`/delivery-attempts/?notification=${notificationId}`),
};
