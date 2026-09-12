import { authFetch } from "./authFetch";

export interface Channel {
  id: string;
  channel_type: "platform" | "community" | "family";
  name: string;
  community: string | null;
  family: string | null;
  created_at: string;
}

export interface ChannelMessage {
  id: string;
  channel: string;
  sender_username: string;
  sender_role: string;
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
 * "Add message channel to all user types and should be a channel from
 * top to down." Every channel a person actually belongs to — their
 * community's, their family's if they're in one, and the platform
 * channel if they're a Community Admin or Platform Admin.
 */
export const messagingApi = {
  myChannels: () => request<Channel[]>(`/messaging/channels/`),
  messages: (channelId: string) => request<ChannelMessage[]>(`/messaging/channels/${channelId}/messages/`),
  post: (channelId: string, content: string) =>
    request<ChannelMessage>(`/messaging/channels/${channelId}/messages/`, { method: "POST", body: JSON.stringify({ content }) }),
};
