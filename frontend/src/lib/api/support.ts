import { authFetch } from "./authFetch";

export interface SupportTicket {
  id: string;
  submitted_by_username: string;
  community_name: string | null;
  subject: string;
  description: string;
  status: "open" | "in_progress" | "resolved" | "closed";
  priority: "low" | "medium" | "high" | "urgent";
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface SupportTicketMessage {
  id: string;
  ticket: string;
  sender_username: string;
  content: string;
  created_at: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authFetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail?.toString() ?? Object.values(body).flat().join(" ") ?? `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

/** "Handle support tickets" — any signed-in user can raise one; only a Platform Admin manages the full queue. */
export const supportApi = {
  myTickets: () => request<SupportTicket[]>(`/support/tickets/`),
  submit: (input: { subject: string; description: string; priority?: string }) =>
    request<SupportTicket>(`/support/tickets/`, { method: "POST", body: JSON.stringify(input) }),
  allTickets: (status?: string) => request<SupportTicket[]>(`/support/tickets/all/${status ? `?status=${status}` : ""}`),
  updateStatus: (ticketId: string, status: string) =>
    request<SupportTicket>(`/support/tickets/${ticketId}/status/`, { method: "POST", body: JSON.stringify({ status }) }),
  messages: (ticketId: string) => request<SupportTicketMessage[]>(`/support/tickets/${ticketId}/messages/`),
  postMessage: (ticketId: string, content: string) =>
    request<SupportTicketMessage>(`/support/tickets/${ticketId}/messages/`, { method: "POST", body: JSON.stringify({ content }) }),
};
