import type { ContributionRulesSummary, ObligationPreview } from "@/types/contributionRules";
import { authFetch } from "./authFetch";
import { unwrapPaginated } from "./unwrapPaginated";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

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
  const json = await res.json();
  return unwrapPaginated<T>(json) as T;
}

export const contributionRulesApi = {
  get: () => request<ContributionRulesSummary>(`/contribution-rules/`),

  updateGeneralRates: (male_amount: string, female_amount: string, reason = "") =>
    request<ContributionRulesSummary>(`/contribution-rules/general-rates/`, {
      method: "POST",
      body: JSON.stringify({ male_amount, female_amount, reason }),
    }),

  updateFamilyTierRates: (input: { head_amount: string; senior_amount: string; junior_amount: string; woman_amount: string; town_leader_amount: string }) =>
    request<ContributionRulesSummary>(`/contribution-rules/family-tier-rates/`, {
      method: "POST",
      body: JSON.stringify(input),
    }),

  setStatusExemption: (status: string, is_exempt: boolean) =>
    request<ContributionRulesSummary>(`/contribution-rules/status-exemption/`, {
      method: "POST",
      body: JSON.stringify({ status, is_exempt }),
    }),

  updateDefaulterThresholds: (warning: number, high_warning: number, flag: number) =>
    request<ContributionRulesSummary>(`/contribution-rules/defaulter-thresholds/`, {
      method: "POST",
      body: JSON.stringify({ warning, high_warning, flag }),
    }),

  preview: (deceased_family_id: string) =>
    request<ObligationPreview>(`/contribution-rules/preview/`, {
      method: "POST",
      body: JSON.stringify({ deceased_family_id }),
    }),
};
