"use client";

import { useCallback, useState } from "react";
import { useInitiateMomoPayment, usePollMomoStatus, useMomoQueryInvalidation, useSubmitMomoOtp } from "@/lib/hooks/useMomo";
import type { MomoPaymentRequest } from "@/lib/api/momo";

/**
 * Reused across three different places a payment can start — the
 * funeral committee's own ledger view, a member's self-service "pay
 * now" prompt, and a collector's front-desk lookup — so it only needs
 * the bare minimum any of those three actually has on hand: which
 * obligation, how much is owed, and a human-readable label for who/what
 * it's for. None of them need to know about each other's data shape.
 */
export function PayViaMomoDialog({
  obligationId,
  balance,
  label,
  onClose,
}: {
  obligationId: string;
  balance: string;
  label: string;
  onClose: () => void;
}) {
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState(balance);
  const [referenceId, setReferenceId] = useState<string | null>(null);
  const [resolvedRequest, setResolvedRequest] = useState<MomoPaymentRequest | null>(null);
  const [otp, setOtp] = useState("");
  const invalidateObligations = useMomoQueryInvalidation();

  const { mutate: initiate, isPending, error } = useInitiateMomoPayment();
  const submitOtp = useSubmitMomoOtp();

  const handleResolved = useCallback(
    (request: MomoPaymentRequest) => {
      setResolvedRequest(request);
      if (request.status === "successful") invalidateObligations();
    },
    [invalidateObligations]
  );

  const pollStatus = usePollMomoStatus(referenceId, handleResolved);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!phone.trim() || !amount) return;
    initiate(
      { obligationId, phoneNumber: phone.trim(), amount },
      { onSuccess: (request) => setReferenceId(request.reference_id) }
    );
  };

  const submitOtpCode = (e: React.FormEvent) => {
    e.preventDefault();
    if (!referenceId || !otp.trim()) return;
    submitOtp.mutate(
      { referenceId, otp: otp.trim() },
      {
        onSuccess: (result) => {
          if (result.status === "successful" || result.status === "failed") {
            handleResolved(result);
          }
          // Still pending after OTP (rare) — re-triggers the polling
          // effect by nudging referenceId through the same value via
          // a fresh reference to the same id.
          setReferenceId(result.reference_id);
        },
      }
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="font-body w-full max-w-sm rounded-sm bg-[var(--surface)] p-6 text-[var(--ink)] shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <h2 className="font-display text-xl">Pay via Mobile Money</h2>
          <button onClick={onClose} className="text-[var(--ink-soft)] hover:text-[var(--ink)]" aria-label="Close">
            ✕
          </button>
        </div>

        {!referenceId && (
          <form onSubmit={submit} className="mt-4 space-y-4">
            <p className="text-sm text-[var(--ink-soft)]">
              {label} owes {formatAmount(balance)}. Enter the phone number to charge — they&apos;ll
              be prompted on that phone to authorize via Mobile Money.
            </p>
            <div>
              <label className="text-sm font-medium">Phone number</label>
              <input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="e.g. 0244000000"
                className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Amount</label>
              <input
                type="number"
                min="0.01"
                step="0.01"
                max={balance}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
              />
            </div>

            {error && <p className="text-sm text-[var(--clay-red)]">{error.message}</p>}

            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={onClose} className="px-3 py-2 text-sm text-[var(--ink-soft)]">
                Cancel
              </button>
              <button
                type="submit"
                disabled={isPending || !phone.trim()}
                className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
              >
                {isPending ? "Sending prompt…" : "Send payment prompt"}
              </button>
            </div>
          </form>
        )}

        {referenceId && pollStatus === "awaiting_otp" && !resolvedRequest && (
          <form onSubmit={submitOtpCode} className="mt-4 space-y-3">
            <p className="text-sm text-[var(--ink-soft)]">
              {phone} should have received a one-time code by SMS — enter it below to finish the payment.
            </p>
            <input
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              placeholder="6-digit code"
              autoFocus
              className="w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
            {submitOtp.isError && <p className="text-sm text-[var(--clay-red)]">{submitOtp.error.message}</p>}
            <button
              type="submit"
              disabled={submitOtp.isPending || !otp.trim()}
              className="w-full rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {submitOtp.isPending ? "Confirming…" : "Confirm code"}
            </button>
          </form>
        )}

        {referenceId && pollStatus !== "awaiting_otp" && !resolvedRequest && (
          <div className="mt-4 space-y-3 text-center">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-[var(--forest)] border-t-transparent" />
            <p className="text-sm">
              {pollStatus === "timed_out"
                ? "Still waiting — this is taking longer than usual. You can close this and check back later; the payment will still be recorded automatically the moment it clears."
                : `Waiting for ${phone} to approve the prompt on their phone…`}
            </p>
            <button onClick={onClose} className="text-sm text-[var(--ink-soft)] underline">
              Close and check later
            </button>
          </div>
        )}

        {resolvedRequest && (
          <div className="mt-4 space-y-3 text-center">
            {resolvedRequest.status === "successful" ? (
              <>
                <p className="font-display text-lg text-[var(--forest)]">Payment confirmed</p>
                <p className="text-sm text-[var(--ink-soft)]">
                  {formatAmount(resolvedRequest.amount)} recorded against {label}&apos;s obligation.
                </p>
              </>
            ) : (
              <>
                <p className="font-display text-lg text-[var(--clay-red)]">Payment not completed</p>
                <p className="text-sm text-[var(--ink-soft)]">
                  The prompt was declined, timed out, or failed. No amount was recorded — you can try again.
                </p>
              </>
            )}
            <button
              onClick={onClose}
              className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white"
            >
              Done
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function formatAmount(value: string): string {
  return `GH₵${Number(value).toFixed(2)}`;
}
