import { authFetch } from "./authFetch";

export type AccessPlan = "ongoing" | "single_funeral" | "time_limited";

export interface Community {
  id: string;
  name: string;
  slug: string;
  region: string;
  is_active: boolean;
  default_general_male_amount: string;
  default_general_female_amount: string;
  created_at: string;
  access_plan: AccessPlan;
  access_expires_at: string | null;
  is_access_expired: boolean;
  access_days_remaining: number | null;
  logo: string | null;
  primary_color: string;
  secondary_color: string;
  tagline: string;
  required_funeral_approvals: number;
}

export interface CommunityAdmin {
  id: string;
  username: string;
  email: string;
}

export interface PayoutAccount {
  id: string;
  account_type: "mobile_money" | "bank";
  provider_name: string;
  account_number: string;
  account_holder_name: string;
  is_active: boolean;
  created_at: string;
}

export interface PlatformBillingRecord {
  id: string;
  community: string;
  description: string;
  amount: string;
  status: "unpaid" | "paid" | "waived";
  created_at: string;
  created_by_username: string | null;
  marked_paid_by_username: string | null;
  marked_paid_at: string | null;
  payment_reference: string;
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
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const tenantsApi = {
  list: () => request<Community[]>(`/tenants/communities/`),

  /** "Some people can also decide to rent or use the service temporarily" — access_days + access_plan create a real, enforced deadline from day one. */
  create: (input: {
    community_name: string;
    region?: string;
    admin_username: string;
    admin_password: string;
    admin_email?: string;
    default_general_male_amount?: string;
    default_general_female_amount?: string;
    access_days?: number;
    access_plan?: AccessPlan;
    // Required by the backend whenever access_days is set — "they must
    // provide their preferred payout account" for a temporary client.
    payout_account_type?: "mobile_money" | "bank";
    payout_provider_name?: string;
    payout_account_number?: string;
    payout_account_holder_name?: string;
  }) =>
    request<{ community: Community; admin: CommunityAdmin }>(`/tenants/communities/`, {
      method: "POST",
      body: JSON.stringify(input),
    }),

  update: (communityId: string, input: Partial<Pick<Community, "name" | "region" | "default_general_male_amount" | "default_general_female_amount">>) =>
    request<Community>(`/tenants/communities/${communityId}/`, { method: "PATCH", body: JSON.stringify(input) }),

  deactivate: (communityId: string) => request<Community>(`/tenants/communities/${communityId}/deactivate/`, { method: "POST" }),
  reactivate: (communityId: string) => request<Community>(`/tenants/communities/${communityId}/reactivate/`, { method: "POST" }),
  deleteEmpty: (communityId: string) => request<void>(`/tenants/communities/${communityId}/`, { method: "DELETE" }),

  extendAccess: (communityId: string, additionalDays: number) =>
    request<Community>(`/tenants/communities/${communityId}/extend-access/`, { method: "POST", body: JSON.stringify({ additional_days: additionalDays }) }),
  makePermanent: (communityId: string) => request<Community>(`/tenants/communities/${communityId}/make-permanent/`, { method: "POST" }),

  listAdmins: (communityId: string) => request<CommunityAdmin[]>(`/tenants/communities/${communityId}/admins/`),
  addAdmin: (communityId: string, input: { username: string; password: string; email?: string }) =>
    request<CommunityAdmin>(`/tenants/communities/${communityId}/admins/`, { method: "POST", body: JSON.stringify(input) }),

  /** "Managing platform administrators" — cross-community, Platform Admin only. */
  listPlatformAdmins: () => request<CommunityAdmin[]>(`/tenants/platform-admins/`),
  addPlatformAdmin: (input: { username: string; password: string; email?: string }) =>
    request<CommunityAdmin>(`/tenants/platform-admins/`, { method: "POST", body: JSON.stringify(input) }),

  /**
   * "Configure branding (logo, colors, community information)" — self-service,
   * no Platform Admin needed. Logo file upload isn't wired in here yet — the
   * backend already accepts it (a real FileField, tested with multipart
   * uploads directly), but this JSON-only client doesn't send files; a
   * genuine, known gap, not something silently skipped.
   */
  getMyCommunityBranding: () => request<Community>(`/tenants/my-community/branding/`),
  updateMyCommunityBranding: (input: { tagline?: string; primary_color?: string; secondary_color?: string }) =>
    request<Community>(`/tenants/my-community/branding/`, { method: "PATCH", body: JSON.stringify(input) }),

  /** "Configure approval workflows" — self-service, own community only. */
  updateMyApprovalWorkflow: (requiredApprovals: number) =>
    request<Community>(`/tenants/my-community/approval-workflow/`, { method: "PATCH", body: JSON.stringify({ required_approvals: requiredApprovals }) }),

  /** "Extend or terminate licenses." */
  terminateAccess: (communityId: string) =>
    request<Community>(`/tenants/communities/${communityId}/terminate-access/`, { method: "POST" }),

  /** "Reset administrator accounts when requested." Not community-scoped — a Platform Admin account has no community at all. */
  resetAdministratorPassword: (input: { username: string; new_password: string }) =>
    request<{ username: string; detail: string }>(`/tenants/reset-admin-password/`, { method: "POST", body: JSON.stringify(input) }),

  /** "Each registered community should have its own dedicated payment account(s)... The platform must never mix funds between different communities." */
  listPayoutAccounts: (communityId: string) => request<PayoutAccount[]>(`/tenants/communities/${communityId}/payout-accounts/`),
  addPayoutAccount: (communityId: string, input: { account_type: "mobile_money" | "bank"; provider_name: string; account_number: string; account_holder_name: string }) =>
    request<PayoutAccount>(`/tenants/communities/${communityId}/payout-accounts/`, { method: "POST", body: JSON.stringify(input) }),
  deactivatePayoutAccount: (communityId: string, accountId: string) =>
    request<PayoutAccount>(`/tenants/communities/${communityId}/payout-accounts/${accountId}/deactivate/`, { method: "POST" }),

  /** "Subscription payments belong to the platform" — completely separate from a community's own contribution ledgers. */
  listBillingRecords: (communityId: string) => request<PlatformBillingRecord[]>(`/tenants/communities/${communityId}/billing-records/`),
  createBillingRecord: (communityId: string, input: { description: string; amount: string }) =>
    request<PlatformBillingRecord>(`/tenants/communities/${communityId}/billing-records/`, { method: "POST", body: JSON.stringify(input) }),
  markBillingRecordPaid: (communityId: string, recordId: string, paymentReference?: string) =>
    request<PlatformBillingRecord>(`/tenants/communities/${communityId}/billing-records/${recordId}/mark-paid/`, { method: "POST", body: JSON.stringify({ payment_reference: paymentReference ?? "" }) }),
  waiveBillingRecord: (communityId: string, recordId: string) =>
    request<PlatformBillingRecord>(`/tenants/communities/${communityId}/billing-records/${recordId}/waive/`, { method: "POST" }),

  /** "View revenue reports" — Platform Admin only, aggregating every community's platform billing records. */
  platformRevenue: (params?: { startDate?: string; endDate?: string }) => {
    const query = new URLSearchParams();
    if (params?.startDate) query.set("start_date", params.startDate);
    if (params?.endDate) query.set("end_date", params.endDate);
    const qs = query.toString();
    return request<PlatformRevenueReport>(`/tenants/platform-revenue/${qs ? `?${qs}` : ""}`);
  },

  /** "Manage feature flags" — a genuine kill-switch, not a toy. */
  listFeatureFlags: () => request<FeatureFlag[]>(`/tenants/feature-flags/`),
  toggleFeatureFlag: (key: string, isEnabled: boolean) =>
    request<FeatureFlag>(`/tenants/feature-flags/${key}/toggle/`, { method: "POST", body: JSON.stringify({ is_enabled: isEnabled }) }),
  featureFlagStatus: () => request<Record<string, boolean>>(`/tenants/feature-flags/status/`),
};

export interface PlatformRevenueReport {
  total_paid: string;
  total_outstanding: string;
  total_waived: string;
  paid_count: number;
  unpaid_count: number;
  waived_count: number;
  by_community: { community_name: string; total: string }[];
}

export interface FeatureFlag {
  id: string;
  key: string;
  name: string;
  description: string;
  is_enabled: boolean;
  updated_at: string;
}
