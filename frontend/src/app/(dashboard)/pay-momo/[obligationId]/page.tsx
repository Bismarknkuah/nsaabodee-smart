"use client";

import "@/styles/family-registry-tokens.css";
import { useCallback, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useInitiateMomoPayment, usePollMomoStatus, useMomoQueryInvalidation, useSubmitMomoOtp } from "@/lib/hooks/useMomo";
import type { MomoPaymentRequest } from "@/lib/api/momo";
import { Field, FIELD_INPUT_CLASS } from "@/components/forms/FormPrimitives";

/**
 * "Should have a full page form that opens as its own page rather
 * than popups." The same flow that used to live in PayViaMomoDialog,
 * now its own page — reached from the funeral committee's ledger, a
 * member's own outstanding-obligations card, or a Collector's front
 * desk lookup, all of which already know the obligation's id, balance,
 * and a label for who/what it's for, so those are passed straight
 * through as query parameters rather than re-fetched here.
 *
 * "Not until a successful MoMo transaction should the money reflect
 * paid." Unchanged from the dialog this replaces: this page only ever
 * shows "Payment confirmed" once the provider's own webhook or polled
 * status check comes back successful (see payments/services.py's
 * _finalize_as_successful, the only place that ever actually records
 * a real ContributionPayment) — sending the prompt itself never marks
 * anything paid, it only starts the wait.
 */
export default function PayMomoPage() {
  const params = useParams<{ obligationId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const obligationId = params.obligationId;
  const balance = searchParams.get("balance") ?? "0";
  const label = searchParams.get("label") ?? "This member";

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
          setReferenceId(result.reference_id);
        },
      }
    );
  };

  return (
    <div className="font-body min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <button onClick={() => router.back()} className="text-sm text-[var(--text-soft)] hover:text-[var(--text)]">
          ← Back
        </button>
        <p className="mt-2 font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--text-soft)]">Mobile Money</p>
        <h1 className="font-display mt-1 text-3xl">Pay via Mobile Money</h1>
      </header>

      <main className="mx-auto max-w-md px-8 py-8">
        {!referenceId && (
          <form onSubmit={submit} className="space-y-4">
            <p className="text-sm text-[var(--text-soft)]">
              {label} owes {formatAmount(balance)}. Enter the phone number to charge — they&apos;ll
              be prompted on that phone to authorize via Mobile Money.
            </p>
            <Field label="Phone number">
              <input
                autoFocus
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="e.g. 0244000000"
                className={FIELD_INPUT_CLASS}
              />
            </Field>
            <Field label="Amount">
              <input
                type="number"
                min="0.01"
                step="0.01"
                max={balance}
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                className={FIELD_INPUT_CLASS}
              />
            </Field>

            {error && <p className="text-sm text-[var(--clay-red)]">{error.message}</p>}

            <div className="flex justify-end gap-2 border-t border-[var(--border)] pt-4">
              <button type="button" onClick={() => router.back()} className="px-3 py-2 text-sm text-[var(--text-soft)]">
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
          <form onSubmit={submitOtpCode} className="space-y-3">
            <p className="text-sm text-[var(--text-soft)]">
              {phone} should have received a one-time code by SMS — enter it below to finish the payment.
            </p>
            <input
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              placeholder="6-digit code"
              autoFocus
              className={FIELD_INPUT_CLASS}
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
          <div className="space-y-3 text-center">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-[var(--forest)] border-t-transparent" />
            <p className="text-sm">
              {pollStatus === "timed_out"
                ? "Still waiting — this is taking longer than usual. You can leave this page and check back later; the payment will still be recorded automatically the moment it clears."
                : `Waiting for ${phone} to approve the prompt on their phone…`}
            </p>
            <button onClick={() => router.back()} className="text-sm text-[var(--text-soft)] underline">
              Leave and check later
            </button>
          </div>
        )}

        {resolvedRequest && (
          <div className="space-y-3 text-center">
            {resolvedRequest.status === "successful" ? (
              <>
                <p className="font-display text-lg text-[var(--forest)]">Payment confirmed</p>
                <p className="text-sm text-[var(--text-soft)]">
                  {formatAmount(resolvedRequest.amount)} recorded against {label}&apos;s obligation.
                </p>
              </>
            ) : (
              <>
                <p className="font-display text-lg text-[var(--clay-red)]">Payment not completed</p>
                <p className="text-sm text-[var(--text-soft)]">
                  The prompt was declined, timed out, or failed. No amount was recorded — you can try again.
                </p>
              </>
            )}
            <button
              onClick={() => router.back()}
              className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white"
            >
              Done
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

function formatAmount(value: string): string {
  return `GH₵${Number(value).toFixed(2)}`;
}
