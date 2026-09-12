import { authFetch } from "./authFetch";

export interface PaymentReversal {
  id: string;
  payment: string;
  payment_receipt_number: string;
  payment_amount: string;
  reason: string;
  status: "pending" | "approved" | "rejected";
  requested_by: string;
  requested_by_username: string;
  requested_at: string;
  decided_by: string | null;
  decided_by_username: string | null;
  decided_at: string | null;
  decision_notes: string;
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
  return res.json() as Promise<T>;
}

/**
 * "If a payment is mistakenly recorded against the wrong member, wrong
 * funeral event, wrong family, or incorrect amount, an authorized
 * administrator should be able to initiate a reversal or correction."
 * The same two-person safeguard as opening a funeral for billing —
 * request, then a DIFFERENT authorized person approves it.
 */
export const paymentReversalsApi = {
  list: () => request<PaymentReversal[]>(`/payment-reversals/`),
  request: (paymentId: string, reason: string) =>
    request<PaymentReversal>(`/payments/${paymentId}/request-reversal/`, { method: "POST", body: JSON.stringify({ reason }) }),
  approve: (reversalId: string, notes?: string) =>
    request<PaymentReversal>(`/payment-reversals/${reversalId}/approve/`, { method: "POST", body: JSON.stringify({ notes: notes ?? "" }) }),
  reject: (reversalId: string, notes?: string) =>
    request<PaymentReversal>(`/payment-reversals/${reversalId}/reject/`, { method: "POST", body: JSON.stringify({ notes: notes ?? "" }) }),
};
