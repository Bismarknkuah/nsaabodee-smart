"use client";

import "@/styles/family-registry-tokens.css";
import { useCallback, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useInitiateMomoGiftPayment, usePollMomoStatus, useMomoGiftQueryInvalidation, useSubmitMomoOtp } from "@/lib/hooks/useMomo";
import { useDonationAccounts } from "@/lib/hooks/useGifts";
import type { MomoPaymentRequest } from "@/lib/api/momo";
import { Field, FIELD_INPUT_CLASS } from "@/components/forms/FormPrimitives";

/**
 * The gift-ledger counterpart to /pay-momo/[obligationId] — its own
 * page rather than a popup, for the same reason. "Not until a
 * successful MoMo transaction should the money reflect paid" holds
 * here identically: nothing here ever creates a GiftDonation directly,
 * only payments/services.py's _finalize_as_successful does, and only
 * once the provider actually confirms it.
 */
export default function PayGiftMomoPage() {
  const params = useParams<{ funeralId: string }>();
  const router = useRouter();
  const funeralId = params.funeralId;

  const { data: donationAccounts } = useDonationAccounts(funeralId);
  const [donorName, setDonorName] = useState("");
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [receivedByMemberId, setReceivedByMemberId] = useState("");
  const [referenceId, setReferenceId] = useState<string | null>(null);
  const [resolvedRequest, setResolvedRequest] = useState<MomoPaymentRequest | null>(null);
  const [otp, setOtp] = useState("");
  const invalidate = useMomoGiftQueryInvalidation();

  const { mutate: initiate, isPending, error } = useInitiateMomoGiftPayment();
  const submitOtp = useSubmitMomoOtp();

  const handleResolved = useCallback(
    (request: MomoPaymentRequest) => {
      setResolvedRequest(request);
      if (request.status === "successful") invalidate();
    },
    [invalidate]
  );
  const pollStatus = usePollMomoStatus(referenceId, handleResolved);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!donorName.trim() || !phone.trim() || !amount) return;
    initiate(
      { funeralId, phoneNumber: phone.trim(), amount, donorName: donorName.trim(), receivedByMemberId: receivedByMemberId || undefined },
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
          if (result.status === "successful" || result.status === "failed") handleResolved(result);
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
        <h1 className="font-display mt-1 text-3xl" style={{ color: "var(--violet)" }}>Gift via Mobile Money</h1>
      </header>

      <main className="mx-auto max-w-md px-8 py-8">
        {!referenceId && (
          <form onSubmit={submit} className="space-y-4">
            <p className="text-sm text-[var(--text-soft)]">
              The donor&apos;s own phone will prompt them to authorize via Mobile Money — no cash changes hands.
            </p>
            <Field label="Donor's name">
              <input autoFocus value={donorName} onChange={(e) => setDonorName(e.target.value)} className={FIELD_INPUT_CLASS} />
            </Field>
            <Field label="Donor's phone">
              <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="e.g. 0244000000" className={FIELD_INPUT_CLASS} />
            </Field>
            <Field label="Amount">
              <input type="number" min="0.01" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} className={FIELD_INPUT_CLASS} />
            </Field>
            {donationAccounts && donationAccounts.length > 0 && (
              <Field label="Give this to (optional)">
                <select value={receivedByMemberId} onChange={(e) => setReceivedByMemberId(e.target.value)} className={FIELD_INPUT_CLASS}>
                  <option value="">General gift (no specific receiver)</option>
                  {donationAccounts.map((a) => <option key={a.id} value={a.member}>{a.member_name}</option>)}
                </select>
              </Field>
            )}
            {error && <p className="text-sm text-[var(--clay-red)]">{error.message}</p>}
            <div className="flex justify-end gap-2 border-t border-[var(--border)] pt-4">
              <button type="button" onClick={() => router.back()} className="px-3 py-2 text-sm text-[var(--text-soft)]">Cancel</button>
              <button type="submit" disabled={isPending} className="rounded-sm px-4 py-2 text-sm font-medium text-white disabled:opacity-60" style={{ backgroundColor: "var(--violet)" }}>
                {isPending ? "Sending prompt…" : "Send payment prompt"}
              </button>
            </div>
          </form>
        )}

        {referenceId && pollStatus === "awaiting_otp" && !resolvedRequest && (
          <form onSubmit={submitOtpCode} className="space-y-3">
            <p className="text-sm text-[var(--text-soft)]">
              {phone} should have received a one-time code by SMS — enter it below to finish the gift.
            </p>
            <input
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              placeholder="6-digit code"
              autoFocus
              className={FIELD_INPUT_CLASS}
            />
            {submitOtp.isError && <p className="text-sm text-[var(--clay-red)]">{submitOtp.error.message}</p>}
            <button type="submit" disabled={submitOtp.isPending || !otp.trim()}
              className="w-full rounded-sm px-4 py-2 text-sm font-medium text-white disabled:opacity-60" style={{ backgroundColor: "var(--violet)" }}>
              {submitOtp.isPending ? "Confirming…" : "Confirm code"}
            </button>
          </form>
        )}

        {referenceId && pollStatus !== "awaiting_otp" && !resolvedRequest && (
          <div className="space-y-3 text-center">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-t-transparent" style={{ borderColor: "var(--violet)" }} />
            <p className="text-sm">
              {pollStatus === "timed_out"
                ? "Still waiting — you can leave this page and check back later; the gift will still be recorded automatically once it clears."
                : `Waiting for ${phone} to approve the prompt…`}
            </p>
            <button onClick={() => router.back()} className="text-sm text-[var(--text-soft)] underline">Leave and check later</button>
          </div>
        )}

        {resolvedRequest && (
          <div className="space-y-3 text-center">
            {resolvedRequest.status === "successful" ? (
              <p className="font-display text-lg" style={{ color: "var(--forest)" }}>Gift confirmed</p>
            ) : (
              <p className="font-display text-lg text-[var(--clay-red)]">Payment not completed</p>
            )}
            <button onClick={() => router.back()} className="rounded-sm px-4 py-2 text-sm font-medium text-white" style={{ backgroundColor: "var(--violet)" }}>Done</button>
          </div>
        )}
      </main>
    </div>
  );
}
