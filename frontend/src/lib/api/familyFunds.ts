import type { FamilyFund, FamilyFundContribution, FamilyFundSummary, FundPaymentMethod } from "@/types/familyFund";
import { authFetch } from "./authFetch";

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

async function openAuthenticatedPdf(path: string): Promise<void> {
  const res = await authFetch(path);
  if (!res.ok) throw new Error(`Could not load the PDF (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export const familyFundsApi = {
  list: (familyId: string) => request<FamilyFund[]>(`/families/${familyId}/funds/`),
  create: (familyId: string, name: string, description?: string) =>
    request<FamilyFund>(`/families/${familyId}/funds/`, { method: "POST", body: JSON.stringify({ name, description }) }),

  listContributions: (familyId: string, fundId: string) =>
    request<FamilyFundContribution[]>(`/families/${familyId}/funds/${fundId}/contributions/`),
  contribute: (familyId: string, fundId: string, input: { member_id: string; amount: string; payment_method?: FundPaymentMethod }) =>
    request<FamilyFundContribution>(`/families/${familyId}/funds/${fundId}/contributions/`, {
      method: "POST",
      body: JSON.stringify({ ...input, client_op_id: crypto.randomUUID() }),
    }),

  summary: (familyId: string, fundId: string) => request<FamilyFundSummary>(`/families/${familyId}/funds/${fundId}/summary/`),

  receiptText: async (familyId: string, fundId: string, contributionId: string) => {
    const res = await authFetch(`/families/${familyId}/funds/${fundId}/contributions/${contributionId}/receipt/`);
    if (!res.ok) throw new Error(`Could not load receipt (${res.status})`);
    const data = await res.json();
    return data.text as string;
  },
  openReceiptPdf: (familyId: string, fundId: string, contributionId: string) =>
    openAuthenticatedPdf(`/families/${familyId}/funds/${fundId}/contributions/${contributionId}/receipt/?export=pdf`),

  assignOfficer: (familyId: string, memberId: string, officerRole: "secretary" | "treasurer") =>
    request(`/families/${familyId}/assign-officer/`, {
      method: "POST",
      body: JSON.stringify({ member_id: memberId, officer_role: officerRole }),
    }),

  /** "Family Head can create: Assistant Family Head... Organizer, Welfare Officer... Custom positions allowed." */
  listOfficerPositions: (familyId: string) => request<FamilyOfficerPosition[]>(`/families/${familyId}/officer-positions/`),
  appointOfficerPosition: (familyId: string, memberId: string, title: string) =>
    request<FamilyOfficerPosition>(`/families/${familyId}/officer-positions/`, {
      method: "POST",
      body: JSON.stringify({ member_id: memberId, title }),
    }),
  removeOfficerPosition: (familyId: string, positionId: string) =>
    request<void>(`/families/${familyId}/officer-positions/${positionId}/`, { method: "DELETE" }),
};

export interface FamilyOfficerPosition {
  id: string;
  family: string;
  member: string;
  member_name: string;
  title: string;
  appointed_by_username: string | null;
  appointed_at: string;
}

export const SUGGESTED_FAMILY_OFFICER_TITLES = [
  "Assistant Family Head",
  "Financial Secretary",
  "Organizer",
  "Welfare Officer",
  "Youth Leader",
  "Women's Leader",
  "Communication Officer",
  "Auditor",
];

// --- Family Funeral Expense Tracking ---

export const familyFuneralExpensesApi = {
  list: (familyId: string, funeralEventId?: string) =>
    request<import("@/types/familyFund").FamilyFuneralExpense[]>(
      `/families/${familyId}/funeral-expenses/${funeralEventId ? `?funeral_event=${funeralEventId}` : ""}`
    ),

  record: (familyId: string, input: {
    funeral_event: string; item_name: string; seller_name: string; seller_contact?: string;
    amount: string; date_purchased: string; paid_by_member_id?: string;
  }) =>
    request<import("@/types/familyFund").FamilyFuneralExpense>(`/families/${familyId}/funeral-expenses/`, {
      method: "POST",
      body: JSON.stringify(input),
    }),

  decide: (familyId: string, expenseId: string, action: "approve" | "reject", reason?: string) =>
    request<import("@/types/familyFund").FamilyFuneralExpense>(`/families/${familyId}/funeral-expenses/${expenseId}/decision/`, {
      method: "POST",
      body: JSON.stringify({ action, reason }),
    }),

  summary: (familyId: string, funeralEventId?: string) =>
    request<import("@/types/familyFund").FuneralExpenditureSummary>(
      `/families/${familyId}/funeral-expenses/summary/${funeralEventId ? `?funeral_event=${funeralEventId}` : ""}`
    ),

  voucherText: async (familyId: string, expenseId: string) => {
    const res = await authFetch(`/families/${familyId}/funeral-expenses/${expenseId}/voucher/`);
    if (!res.ok) throw new Error(`Could not load voucher (${res.status})`);
    const data = await res.json();
    return data.text as string;
  },
  openVoucherPdf: async (familyId: string, expenseId: string) => {
    const res = await authFetch(`/families/${familyId}/funeral-expenses/${expenseId}/voucher/?export=pdf`);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `Could not load voucher (${res.status})`);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank");
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  },
};

export interface FamilyFinancialOverview {
  family_id: string;
  family_name: string;
  total_fund_contributions: string;
  total_approved_expenses: string;
  total_pending_expenses: string;
  net_position: string;
}

export const familyFinancialOverviewApi = {
  get: (familyId: string, funeralEventId?: string) =>
    request<FamilyFinancialOverview>(
      `/families/${familyId}/financial-overview/${funeralEventId ? `?funeral_event=${funeralEventId}` : ""}`
    ),
};
