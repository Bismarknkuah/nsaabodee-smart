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
  list: (filters?: { search?: string; family?: string; status?: MemberStatus; defaulter_tier?: DefaulterTier; gender?: "male" | "female"; sort_by?: string }) => {
    const params = new URLSearchParams();
    if (filters?.search) params.set("search", filters.search);
    if (filters?.family) params.set("family", filters.family);
    if (filters?.status) params.set("status", filters.status);
    if (filters?.defaulter_tier) params.set("defaulter_tier", filters.defaulter_tier);
    if (filters?.gender) params.set("gender", filters.gender);
    if (filters?.sort_by) params.set("sort_by", filters.sort_by);
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

  /** 'If he doesn't get change, money balance should be credited to the member's wallet.' */
  wallet: (id: string) =>
    request<{ member_id: string; balance: string; transactions: { id: string; kind: string; amount: string; note: string; created_at: string }[] }>(
      `/members/${id}/wallet/`
    ),

  /** 'Since you become a town elder the community admin or community executive should be able to transfer you to be part of the town elders ledger.' */
  transferToTownElder: (id: string, title: "chief" | "queen_mother" | "linguist" | "other") =>
    request<Member>(`/members/${id}/transfer-to-town-elder/`, { method: "POST", body: JSON.stringify({ title }) }),

  /** 'The town leader should also have user management... to manage the town elders ledger' — includes taking someone off it. */
  removeFromTownElder: (id: string) =>
    request<Member>(`/members/${id}/remove-from-town-elder/`, { method: "POST" }),
};

export interface CollectorNomination {
  id: string;
  member_id: string;
  member_name: string;
  collector_type: "general" | "family" | "donation" | "town_elder";
  scoped_family_name: string | null;
  status: "pending" | "approved" | "rejected";
  nominated_by: string | null;
  created_at: string;
  approvals: { decided_by: string; decision: "approve" | "reject"; decided_at: string }[];
}

/** 'The collectors should be in 4 categories... for transparency, when one creates an account he needs other executives to approve it before that account can start collecting money.' */
export const collectorNominationsApi = {
  list: () => request<CollectorNomination[]>(`/members/collector-nominations/`),
  nominate: (memberId: string, collectorType: CollectorNomination["collector_type"]) =>
    request<CollectorNomination>(`/members/collector-nominations/`, {
      method: "POST",
      body: JSON.stringify({ member_id: memberId, collector_type: collectorType }),
    }),
  decide: (nominationId: string, decision: "approve" | "reject") =>
    request<CollectorNomination>(`/members/collector-nominations/${nominationId}/decide/`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    }),
};
