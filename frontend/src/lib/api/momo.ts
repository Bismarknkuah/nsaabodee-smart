import { authFetch } from "./authFetch";

export type MomoStatus = "pending" | "awaiting_otp" | "successful" | "failed";
export type MomoTargetType = "contribution" | "gift";

export interface MomoPaymentRequest {
  id: string;
  target_type: MomoTargetType;
  obligation: string | null;
  funeral_event: string | null;
  donor_name: string;
  received_by_member: string | null;
  reference_id: string;
  phone_number: string;
  amount: string;
  status: MomoStatus;
  created_at: string;
  updated_at: string;
}

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

export const momoApi = {
  requestToPay: (obligationId: string, phoneNumber: string, amount: string) =>
    request<MomoPaymentRequest>(`/payments/momo/request-to-pay/`, {
      method: "POST",
      body: JSON.stringify({ obligation_id: obligationId, phone_number: phoneNumber, amount }),
    }),

  /** Ledger 2 via MoMo — "some people can also pay via momo," including gifts earmarked to a registered donation-account holder. */
  requestGiftToPay: (
    funeralId: string,
    input: { phoneNumber: string; amount: string; donorName: string; receivedByMemberId?: string }
  ) =>
    request<MomoPaymentRequest>(`/payments/momo/gift-request-to-pay/`, {
      method: "POST",
      body: JSON.stringify({
        funeral_id: funeralId,
        phone_number: input.phoneNumber,
        amount: input.amount,
        donor_name: input.donorName,
        received_by_member_id: input.receivedByMemberId,
      }),
    }),

  checkStatus: (referenceId: string) =>
    request<MomoPaymentRequest>(`/payments/momo/status/${referenceId}/`),

  /** The one extra step MTN mobile money (via Paystack) needs when a request comes back "awaiting_otp". */
  submitOtp: (referenceId: string, otp: string) =>
    request<MomoPaymentRequest>(`/payments/momo/submit-otp/${referenceId}/`, {
      method: "POST",
      body: JSON.stringify({ otp }),
    }),
};
