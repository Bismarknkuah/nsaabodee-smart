import { authFetch } from "./authFetch";
import { unwrapPaginated } from "./unwrapPaginated";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authFetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail?.toString() ?? Object.values(body).flat().join(" ") ?? `Request failed (${res.status})`);
  }
  const json = await res.json();
  return unwrapPaginated<T>(json) as T;
}

export type ContributionFrequency = "one_time" | "monthly" | "quarterly" | "annual";
export type ContributionAmountType = "fixed" | "flexible";
export type CampaignStatus = "pending_approval" | "family_approved" | "active" | "rejected" | "closed";

export interface ContributionCategory {
  id: string;
  name: string;
  purpose: string;
  is_mandatory: boolean;
  amount_type: ContributionAmountType;
  fixed_amount: string | null;
  frequency: ContributionFrequency;
  required_family_approvals: number;
  is_active: boolean;
  created_at: string;
}

export interface ContributionCampaign {
  id: string;
  category: string;
  category_name: string;
  community: string;
  family: string | null;
  family_name: string | null;
  title: string;
  amount: string;
  due_date: string | null;
  status: CampaignStatus;
  initiated_by_username: string | null;
  created_at: string;
}

export interface WelfareObligation {
  id: string;
  campaign: string;
  member: string;
  member_name: string;
  expected_amount: string;
  amount_paid: string;
  balance: string;
  payment_status: "unpaid" | "partial" | "paid";
  generated_at: string;
}

/**
 * 'Nsaabodeɛ Smart must not be limited to funeral contributions...
 * every community should also be able to use the platform for general
 * welfare and community development contributions.' A genuinely
 * separate ledger from funeral contributions and gift donations —
 * every campaign belongs to exactly one category, so funds are never
 * mixed between contribution types.
 */
export const welfareApi = {
  listCategories: () => request<ContributionCategory[]>(`/welfare/categories/`),
  createCategory: (input: {
    name: string; purpose?: string; is_mandatory?: boolean; amount_type?: ContributionAmountType;
    fixed_amount?: string; frequency?: ContributionFrequency; required_family_approvals?: number;
  }) => request<ContributionCategory>(`/welfare/categories/`, { method: "POST", body: JSON.stringify(input) }),

  listCampaigns: () => request<ContributionCampaign[]>(`/welfare/campaigns/`),

  /** "When the community creates it, it affects all the community." No approval needed — active immediately. */
  initiateCommunityCampaign: (input: { category_id: string; title: string; amount?: string; due_date?: string }) =>
    request<ContributionCampaign>(`/welfare/campaigns/community-wide/`, { method: "POST", body: JSON.stringify(input) }),

  /** "Any family can also use it for welfare... it should only be within his jurisdiction." Starts pending approval. */
  initiateFamilyCampaign: (familyId: string, input: { category_id: string; title: string; amount?: string; due_date?: string }) =>
    request<ContributionCampaign>(`/welfare/families/${familyId}/campaigns/`, { method: "POST", body: JSON.stringify(input) }),

  /** "It needs the approval of two other family executives before his family members get billed." */
  decideCampaign: (campaignId: string, approve: boolean) =>
    request<ContributionCampaign>(`/welfare/campaigns/${campaignId}/decide/`, { method: "POST", body: JSON.stringify({ approve }) }),

  /** 'Has to be approved by the community admin before it works for his community members' — the second, final gate after the family's own executives sign off. */
  pendingCommunityAdminApprovals: () => request<ContributionCampaign[]>(`/welfare/campaigns/pending-admin-approval/`),

  adminApproveCampaign: (campaignId: string, approve: boolean = true) =>
    request<ContributionCampaign>(`/welfare/campaigns/${campaignId}/admin-approve/`, { method: "POST", body: JSON.stringify({ approve }) }),

  listObligations: (campaignId: string) => request<WelfareObligation[]>(`/welfare/campaigns/${campaignId}/obligations/`),

  recordPayment: (obligationId: string, input: { amount: string; method: "cash" | "mobile_money" | "bank" | "other" }) =>
    request<WelfareObligation>(`/welfare/obligations/${obligationId}/record-payment/`, { method: "POST", body: JSON.stringify(input) }),
};
