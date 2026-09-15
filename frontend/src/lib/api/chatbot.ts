import { authFetch } from "./authFetch";

export interface ChatbotMessage {
  id: string;
  role: "user" | "assistant";
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
    const message = body.detail?.toString() ?? Object.values(body).flat().join(" ") ?? `Request failed (${res.status})`;
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

/**
 * "Add chatbot to all user types." A help assistant, not a
 * data-querying agent — it explains how to use the platform and never
 * has access to anyone's actual balances or records.
 */
export const chatbotApi = {
  history: () => request<ChatbotMessage[]>(`/ai/chatbot/history/`),
  ask: (message: string) => request<ChatbotMessage>(`/ai/chatbot/`, { method: "POST", body: JSON.stringify({ message }) }),
};
