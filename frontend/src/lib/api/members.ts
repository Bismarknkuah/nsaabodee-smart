import type { DigitalMembershipCard, DefaulterTier, Member, MemberStatus } from "@/types/member";
import { authFetch } from "./authFetch";
import { unwrapPaginated } from "./unwrapPaginated";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authFetch(path, {
    ...init,
    headers: init?.body instanceof FormData ? init.headers : { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const message = body.detail?.toString() ?? Object.values(body).flat().join(" ") ?? `Request failed (${res.status})`;
    throw new Error(message);
  }
  const json = await res.json();
  return unwrapPaginated<T>(json) as T;
}

export const membersApi = {
  list: (filters?: { search?: string; family?: string; status?: MemberStatus; defaulter_tier?: DefaulterTier }) => {
    const params = new URLSearchParams();
    if (filters?.search) params.set("search", filters.search);
    if (filters?.family) params.set("family", filters.family);
    if (filters?.status) params.set("status", filters.status);
    if (filters?.defaulter_tier) params.set("defaulter_tier", filters.defaulter_tier);
    const qs = params.toString();
    return request<Member[]>(`/members/${qs ? `?${qs}` : ""}`);
  },

  get: (id: string) => request<Member>(`/members/${id}/`),

  register: (formData: FormData) => request<Member>(`/members/`, { method: "POST", body: formData }),

  update: (id: string, fields: Partial<Member>) =>
    request<Member>(`/members/${id}/`, { method: "PATCH", body: JSON.stringify(fields) }),

  card: (id: string) => request<DigitalMembershipCard>(`/members/${id}/card/`),

  linkUser: (id: string, username: string) =>
    request<Member>(`/members/${id}/link-user/`, { method: "POST", body: JSON.stringify({ username }) }),

  /** "Specific roles to select when the community admin wants to assign a role... more options as he supervises and manages the community system." */
  assignRole: (id: string, input: { role: string; username?: string; password?: string }) =>
    request<{ member_id: string; role: string; username: string }>(`/members/${id}/assign-role/`, { method: "POST", body: JSON.stringify(input) }),

  /** "Assign and revoke roles and permissions." */
  revokeRole: (id: string) =>
    request<{ member_id: string; role: string; username: string }>(`/members/${id}/revoke-role/`, { method: "POST" }),

  defaulters: () => request<Member[]>(`/members/defaulters/`),
};
