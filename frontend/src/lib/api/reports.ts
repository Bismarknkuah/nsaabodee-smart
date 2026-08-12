import type { CollectionsReport, ExpenseStatement, FamilyStatement, FuneralDailyBreakdown, FuneralLedgerBreakdown, MyReceiptsResponse, OutstandingMembersReport, OutstandingObligation } from "@/types/reports";
import { authFetch } from "./authFetch";
import { unwrapPaginated } from "./unwrapPaginated";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authFetch(path, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail?.toString() ?? `Request failed (${res.status})`);
  }
  const json = await res.json();
  return unwrapPaginated<T>(json) as T;
}

/**
 * PDF/statement "downloads" can no longer be plain `<a href>` links now
 * that auth is a bearer token rather than a cookie — a browser
 * navigating directly to a URL never attaches a custom Authorization
 * header, so a plain link to a protected PDF endpoint would just get a
 * 401. This fetches the PDF through the same authenticated path as
 * everything else, then opens the result (a Blob) in a new tab via an
 * object URL — from the person's point of view it still opens exactly
 * like clicking a normal download link.
 */
async function openAuthenticatedPdf(path: string): Promise<void> {
  const res = await authFetch(path);
  if (!res.ok) throw new Error(`Could not load the PDF (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export const reportsApi = {
  daily: (date: string) => request<CollectionsReport>(`/reports/collections/daily/?date=${date}`),
  weekly: (weekStart: string) => request<CollectionsReport>(`/reports/collections/weekly/?week_start=${weekStart}`),
  monthly: (year: number, month: number) => request<CollectionsReport>(`/reports/collections/monthly/?year=${year}&month=${month}`),
  annual: (year: number) => request<CollectionsReport>(`/reports/collections/annual/?year=${year}`),
  myPerformance: (startDate: string, endDate: string) =>
    request<CollectionsReport>(`/reports/collections/my-performance/?start_date=${startDate}&end_date=${endDate}`),
  familyStatement: (familyId: string) => request<FamilyStatement>(`/reports/families/${familyId}/statement/`),
  myOutstandingObligations: () => request<OutstandingObligation[]>(`/my-obligations/`),
  memberOutstandingObligations: (memberId: string) =>
    request<OutstandingObligation[]>(`/reports/members/${memberId}/outstanding-obligations/`),
  funeralLedgerBreakdown: (funeralId: string) =>
    request<FuneralLedgerBreakdown>(`/reports/funerals/${funeralId}/ledger-breakdown/`),
  /** "It starts Friday and closes Sunday evening but they should be able to know the amount they received each day." */
  funeralDailyBreakdown: (funeralId: string) =>
    request<FuneralDailyBreakdown>(`/reports/funerals/${funeralId}/daily-breakdown/`),
  outstandingMembers: () => request<OutstandingMembersReport>(`/reports/outstanding-members/`),
  expenseStatement: (startDate: string, endDate: string) =>
    request<ExpenseStatement>(`/reports/expenses/?start_date=${startDate}&end_date=${endDate}`),
  myReceipts: () => request<MyReceiptsResponse>(`/my-receipts/`),

  contributionReceiptText: async (paymentId: string) => {
    const res = await authFetch(`/receipts/contribution-payments/${paymentId}/text/`);
    return res.text();
  },
  giftReceiptText: async (donationId: string) => {
    const res = await authFetch(`/receipts/gift-donations/${donationId}/text/`);
    return res.text();
  },

  openContributionReceiptPdf: (paymentId: string) => openAuthenticatedPdf(`/receipts/contribution-payments/${paymentId}/pdf/`),
  openGiftReceiptPdf: (donationId: string) => openAuthenticatedPdf(`/receipts/gift-donations/${donationId}/pdf/`),
  openFamilyStatementPdf: (familyId: string) => openAuthenticatedPdf(`/reports/families/${familyId}/statement/?export=pdf`),
  openCollectionsPdf: (period: "daily" | "weekly" | "monthly" | "annual", params: string) =>
    openAuthenticatedPdf(`/reports/collections/${period}/?export=pdf&${params}`),
};
