const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";
import { authFetch } from "./authFetch";

export interface PlanInterestSubmission {
  id: string;
  plan_type: "single_funeral" | "community" | "multi_community";
  name: string;
  email: string;
  phone: string;
  message: string;
  created_at: string;
  contacted: boolean;
}

/**
 * "Make sure all coming soon are completely designed." Turns each
 * pricing plan's disabled button into real, actionable lead capture —
 * deliberately plain fetch() for submission, since anyone on the
 * public homepage needs to be able to register interest with no login.
 */
export const planInterestApi = {
  submit: async (input: { plan_type: string; name: string; email?: string; phone?: string; message?: string }): Promise<void> => {
    const res = await fetch(`${BASE}/api/tenants/plan-interest/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail?.toString() ?? body.name?.[0] ?? body.non_field_errors?.[0] ?? "Could not submit — please try again.");
    }
  },

  listAll: async (): Promise<PlanInterestSubmission[]> => {
    const res = await authFetch("/tenants/plan-interest/manage/");
    if (!res.ok) throw new Error("Could not load plan interest submissions.");
    return res.json();
  },

  markContacted: async (submissionId: string): Promise<void> => {
    const res = await authFetch(`/tenants/plan-interest/${submissionId}/mark-contacted/`, { method: "POST" });
    if (!res.ok) throw new Error("Could not update this submission.");
  },
};
