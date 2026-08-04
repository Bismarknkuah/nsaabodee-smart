import type {
  DonationAccountRegistration,
  DonorCategory,
  GiftCategoryBreakdown,
  GiftDonation,
  GiftPaymentMethod,
  GiftSummary,
  MyDonationsReceived,
  ReceiverDonationList,
} from "@/types/gift";
import { authFetch } from "./authFetch";
import { unwrapPaginated } from "./unwrapPaginated";

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

/**
 * A plain `<a href>` can't carry the bearer token, so PDF "downloads"
 * fetch through the same authenticated path as everything else and
 * open the result as a Blob — see reports.ts's openAuthenticatedPdf for
 * the original version of this same pattern.
 */
async function openAuthenticatedPdf(path: string): Promise<void> {
  const res = await authFetch(path);
  if (!res.ok) throw new Error(`Could not load the PDF (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export const giftsApi = {
  /**
   * Only returns data at all for this family's own head, Community
   * Admin+, or a superuser — the backend returns 403 for the rest of
   * the funeral committee, per "the funeral committee should have
   * access to all the money paid except the donations."
   */
  list: (funeralId: string, category?: DonorCategory) =>
    request<GiftDonation[]>(`/funerals/${funeralId}/gifts/${category ? `?category=${category}` : ""}`),

  /**
   * "Unless that information is required for reconciliation, auditing,
   * or legal compliance." For a temporary/rental event, the plain
   * `list` above returns anonymized donor names ("Donor #1") — this
   * reveals the real names, but only with a stated reason, and every
   * call is written to the audit log.
   */
  listWithReconciliation: (funeralId: string, reason: string) =>
    request<GiftDonation[]>(`/funerals/${funeralId}/gifts/reconciliation/?reason=${encodeURIComponent(reason)}`),

  summary: (funeralId: string) => request<GiftSummary>(`/funerals/${funeralId}/gifts/summary/`),

  categoryBreakdown: (funeralId: string) =>
    request<GiftCategoryBreakdown>(`/funerals/${funeralId}/gifts/by-category/`),

  record: (
    funeralId: string,
    input: {
      donor_name: string;
      donor_phone?: string;
      donor_member_id?: string;
      donor_category?: DonorCategory;
      donor_hometown?: string;
      connected_relative_name?: string;
      relationship_to_recipient?: string;
      received_by_member_id?: string;
      amount_cash?: string;
      gift_item?: string;
      estimated_item_value?: string;
      payment_method?: GiftPaymentMethod;
      client_op_id?: string;
    }
  ) =>
    request<GiftDonation>(`/funerals/${funeralId}/gifts/`, {
      method: "POST",
      body: JSON.stringify(input),
    }),

  // --- Donation Accounts ("temporary donation account") ---

  listDonationAccounts: (funeralId: string) =>
    request<DonationAccountRegistration[]>(`/funerals/${funeralId}/donation-accounts/`),

  registerDonationAccount: (funeralId: string, memberId: string) =>
    request<DonationAccountRegistration>(`/funerals/${funeralId}/donation-accounts/`, {
      method: "POST",
      body: JSON.stringify({ member_id: memberId }),
    }),

  /** "Activated when the family heads approve it" — a Family Head's own approval queue, across every funeral their family's members are registered for. */
  pendingDonationAccounts: () => request<DonationAccountRegistration[]>(`/donation-accounts/pending/`),

  approveDonationAccount: (registrationId: string) =>
    request<DonationAccountRegistration>(`/donation-accounts/${registrationId}/approve/`, { method: "POST" }),

  // --- "Any amount paid should reflect on the person dashboard" ---
  myDonationsReceived: () => request<MyDonationsReceived>(`/my-donations-received/`),
  openMyDonationsReceivedPdf: () => openAuthenticatedPdf(`/my-donations-received/?export=pdf`),

  // --- "After the funeral all should be able to print receipts to all those who received donations" ---
  allReceiversStatement: (funeralId: string) =>
    request<ReceiverDonationList[]>(`/funerals/${funeralId}/donation-accounts/all-receivers-statement/`),
  openAllReceiversStatementPdf: (funeralId: string) =>
    openAuthenticatedPdf(`/funerals/${funeralId}/donation-accounts/all-receivers-statement/?export=pdf`),
};
