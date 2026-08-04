import type { Family, FamilyAuditLogEntry } from "@/types/family";
import { authFetch } from "./authFetch";
import { unwrapPaginated } from "./unwrapPaginated";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authFetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const message =
      body.detail?.toString() ??
      Object.values(body).flat().join(" ") ??
      `Request failed (${res.status})`;
    throw new Error(message);
  }

  if (res.status === 204) return undefined as T;
  const json = await res.json();
  return unwrapPaginated<T>(json) as T;
}

export const familiesApi = {
  list: (includeInactive = false) =>
    request<Family[]>(`/families/?include_inactive=${includeInactive}`),

  create: (input: { name: string; description?: string }) =>
    request<Family>(`/families/`, { method: "POST", body: JSON.stringify(input) }),

  /** "The system must require the registration of the Family Head as part of the process." The recommended way to create a family now — name plus a genuinely required head profile and login, created together. */
  registerWithHead: (input: {
    name: string;
    description?: string;
    head_full_name: string;
    head_gender: "male" | "female";
    head_username: string;
    head_password: string;
    head_phone?: string;
    head_email?: string;
    head_ghana_card_number?: string;
    head_address?: string;
    head_occupation?: string;
    head_date_of_birth?: string;
  }) =>
    request<{ family: Family; head_member_id: string; head_username: string }>(`/families/register-with-head/`, {
      method: "POST", body: JSON.stringify(input),
    }),

  rename: (id: string, name: string) =>
    request<Family>(`/families/${id}/rename/`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  merge: (sourceId: string, targetFamilyId: string) =>
    request<Family>(`/families/${sourceId}/merge/`, {
      method: "POST",
      body: JSON.stringify({ target_family_id: targetFamilyId }),
    }),

  deactivate: (id: string) =>
    request<Family>(`/families/${id}/deactivate/`, { method: "POST" }),

  reactivate: (id: string) =>
    request<Family>(`/families/${id}/reactivate/`, { method: "POST" }),

  remove: (id: string, force = false) =>
    request<void>(`/families/${id}/`, {
      method: "DELETE",
      body: JSON.stringify({ force }),
    }),

  transferMembers: (targetFamilyId: string, memberIds: string[]) =>
    request<Family>(`/families/${targetFamilyId}/transfer-members/`, {
      method: "POST",
      body: JSON.stringify({ member_ids: memberIds, target_family_id: targetFamilyId }),
    }),

  assignHead: (id: string, memberId: string) =>
    request<Family>(`/families/${id}/assign-head/`, {
      method: "POST",
      body: JSON.stringify({ member_id: memberId }),
    }),

  auditLogs: (id: string) => request<FamilyAuditLogEntry[]>(`/families/${id}/audit-logs/`),

  recommendRate: (id: string, amount: string) =>
    request<Family>(`/families/${id}/recommend-rate/`, { method: "POST", body: JSON.stringify({ amount }) }),

  approveRate: (id: string, amount?: string) =>
    request<Family>(`/families/${id}/approve-rate/`, {
      method: "POST",
      body: JSON.stringify(amount ? { amount } : {}),
    }),

  rejectRate: (id: string, reason = "") =>
    request<Family>(`/families/${id}/reject-rate/`, { method: "POST", body: JSON.stringify({ reason }) }),
};
