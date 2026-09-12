"use client";

import { useCallback, useState } from "react";
import { useInitiateMomoGiftPayment, usePollMomoStatus, useMomoGiftQueryInvalidation, useSubmitMomoOtp } from "@/lib/hooks/useMomo";
import { useDonationAccounts } from "@/lib/hooks/useGifts";
import type { MomoPaymentRequest } from "@/lib/api/momo";

export function PayGiftViaMomoDialog({ funeralId, onClose }: { funeralId: string; onClose: () => void }) {
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="font-body w-full max-w-sm rounded-sm bg-[var(--surface)] p-6 text-[var(--ink)] shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <h2 className="font-display text-xl" style={{ color: "var(--violet)" }}>Gift via Mobile Money</h2>
          <button onClick={onClose} className="text-[var(--ink-soft)] hover:text-[var(--ink)]" aria-label="Close">✕</button>
        </div>

        {!referenceId && (
          <form onSubmit={submit} className="mt-4 space-y-4">
            <p className="text-sm text-[var(--ink-soft)]">
              The donor&apos;s own phone will prompt them to authorize via Mobile Money — no cash changes hands.
            </p>
            <div>
              <label className="text-sm font-medium">Donor&apos;s name</label>
              <input value={donorName} onChange={(e) => setDonorName(e.target.value)}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]" />
            </div>
            <div>
              <label className="text-sm font-medium">Donor&apos;s phone</label>
              <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="e.g. 0244000000"
                className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]" />
            </div>
            <div>
              <label className="text-sm font-medium">Amount</label>
              <input type="number" min="0.01" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]" />
            </div>
            {donationAccounts && donationAccounts.length > 0 && (
              <div>
                <label className="text-sm font-medium">Give this to (optional)</label>
                <select value={receivedByMemberId} onChange={(e) => setReceivedByMemberId(e.target.value)}
                  className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]">
                  <option value="">General gift (no specific receiver)</option>
                  {donationAccounts.map((a) => <option key={a.id} value={a.member}>{a.member_name}</option>)}
                </select>
              </div>
            )}
            {error && <p className="text-sm text-[var(--clay-red)]">{error.message}</p>}
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={onClose} className="px-3 py-2 text-sm text-[var(--ink-soft)]">Cancel</button>
              <button type="submit" disabled={isPending} className="rounded-sm px-4 py-2 text-sm font-medium text-white disabled:opacity-60" style={{ backgroundColor: "var(--violet)" }}>
                {isPending ? "Sending prompt…" : "Send payment prompt"}
              </button>
            </div>
          </form>
        )}

        {referenceId && pollStatus === "awaiting_otp" && !resolvedRequest && (
          <form onSubmit={submitOtpCode} className="mt-4 space-y-3">
            <p className="text-sm text-[var(--ink-soft)]">
              {phone} should have received a one-time code by SMS — enter it below to finish the gift.
            </p>
            <input
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              placeholder="6-digit code"
              autoFocus
              className="w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
            {submitOtp.isError && <p className="text-sm text-[var(--clay-red)]">{submitOtp.error.message}</p>}
            <button type="submit" disabled={submitOtp.isPending || !otp.trim()}
              className="w-full rounded-sm px-4 py-2 text-sm font-medium text-white disabled:opacity-60" style={{ backgroundColor: "var(--violet)" }}>
              {submitOtp.isPending ? "Confirming…" : "Confirm code"}
            </button>
          </form>
        )}

        {referenceId && pollStatus !== "awaiting_otp" && !resolvedRequest && (
          <div className="mt-4 space-y-3 text-center">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-t-transparent" style={{ borderColor: "var(--violet)" }} />
            <p className="text-sm">
              {pollStatus === "timed_out"
                ? "Still waiting — you can close this and check back later; the gift will still be recorded automatically once it clears."
                : `Waiting for ${phone} to approve the prompt…`}
            </p>
            <button onClick={onClose} className="text-sm text-[var(--ink-soft)] underline">Close and check later</button>
          </div>
        )}

        {resolvedRequest && (
          <div className="mt-4 space-y-3 text-center">
            {resolvedRequest.status === "successful" ? (
              <p className="font-display text-lg" style={{ color: "var(--forest)" }}>Gift confirmed</p>
            ) : (
              <p className="font-display text-lg text-[var(--clay-red)]">Payment not completed</p>
            )}
            <button onClick={onClose} className="rounded-sm px-4 py-2 text-sm font-medium text-white" style={{ backgroundColor: "var(--violet)" }}>Done</button>
          </div>
        )}
      </div>
    </div>
  );
}
