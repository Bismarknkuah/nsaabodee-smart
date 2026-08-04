"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { paymentReversalsApi } from "@/lib/api/paymentReversals";

/**
 * "Every reversal must be logged with the reason, the user who
 * performed it, the original transaction reference, the date, and the
 * approval history to maintain a complete audit trail." This page IS
 * that audit trail, plainly laid out — nothing here is ever deleted or
 * hidden once decided, approved and rejected requests stay visible
 * alongside pending ones.
 */
export default function PaymentReversalsPage() {
  const qc = useQueryClient();
  const { data: reversals, isLoading } = useQuery({ queryKey: ["payment-reversals"], queryFn: paymentReversalsApi.list });

  const [paymentId, setPaymentId] = useState("");
  const [reason, setReason] = useState("");
  const [requestError, setRequestError] = useState<string | null>(null);

  const requestReversal = useMutation({
    mutationFn: () => paymentReversalsApi.request(paymentId, reason),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["payment-reversals"] }); setPaymentId(""); setReason(""); setRequestError(null); },
    onError: (err: Error) => setRequestError(err.message),
  });
  const approve = useMutation({
    mutationFn: (id: string) => paymentReversalsApi.approve(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payment-reversals"] }),
  });
  const reject = useMutation({
    mutationFn: (id: string) => paymentReversalsApi.reject(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payment-reversals"] }),
  });

  const pending = reversals?.filter((r) => r.status === "pending") ?? [];
  const decided = reversals?.filter((r) => r.status !== "pending") ?? [];

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Financial Integrity</p>
        <h1 className="font-display mt-1 text-4xl">Payment Reversals</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          A payment recorded against the wrong member, funeral, family, or amount can be
          corrected here. Nothing is ever deleted — the original payment stays exactly as
          it was recorded; a reversal only takes effect once a different authorized person
          approves it.
        </p>
      </header>

      <main className="mx-auto max-w-3xl px-8 py-8">
        <section className="rounded-sm border border-[var(--rule)] bg-white p-6">
          <h2 className="font-display text-xl">Request a reversal</h2>
          <form
            onSubmit={(e) => { e.preventDefault(); requestReversal.mutate(); }}
            className="mt-4 space-y-3"
          >
            <div>
              <label className="text-sm font-medium">Payment ID</label>
              <input
                value={paymentId}
                onChange={(e) => setPaymentId(e.target.value)}
                placeholder="The receipt's payment reference"
                className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Reason</label>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                rows={2}
                placeholder="e.g. Recorded against the wrong member — should have been..."
                className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
              />
              <p className="mt-1 text-xs text-[var(--ink-soft)]">This becomes part of the permanent audit trail.</p>
            </div>
            {requestError && <p className="text-sm text-[var(--clay-red)]">{requestError}</p>}
            <button
              type="submit"
              disabled={requestReversal.isPending || !paymentId || !reason.trim()}
              className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {requestReversal.isPending ? "Submitting…" : "Request reversal"}
            </button>
          </form>
        </section>

        <section className="mt-8">
          <h2 className="font-display text-xl">Pending approval</h2>
          {isLoading ? (
            <p className="mt-2 text-sm text-[var(--ink-soft)]">Loading…</p>
          ) : pending.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--ink-soft)]">Nothing awaiting a decision.</p>
          ) : (
            <ul className="mt-3 space-y-3">
              {pending.map((r) => (
                <li key={r.id} className="rounded-sm border border-[var(--gold)] bg-[var(--gold-soft)] p-4">
                  <p className="text-sm font-medium">
                    Receipt {r.payment_receipt_number} — GHS {r.payment_amount}
                  </p>
                  <p className="mt-1 text-sm">{r.reason}</p>
                  <p className="mt-2 text-xs text-[var(--ink-soft)]">
                    Requested by {r.requested_by_username} on {new Date(r.requested_at).toLocaleDateString()}
                  </p>
                  <div className="mt-2 flex gap-3">
                    <button onClick={() => approve.mutate(r.id)} className="text-sm font-medium" style={{ color: "var(--forest)" }}>
                      Approve
                    </button>
                    <button onClick={() => reject.mutate(r.id)} className="text-sm font-medium text-[var(--clay-red)]">
                      Reject
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>

        {decided.length > 0 && (
          <section className="mt-8">
            <h2 className="font-display text-xl">Decided</h2>
            <ul className="mt-3 space-y-2">
              {decided.map((r) => (
                <li key={r.id} className="rounded-sm border border-[var(--rule)] bg-white p-3 text-sm">
                  <span className={r.status === "approved" ? "font-medium" : "font-medium text-[var(--clay-red)]"} style={r.status === "approved" ? { color: "var(--forest)" } : undefined}>
                    {r.status === "approved" ? "Approved" : "Rejected"}
                  </span>
                  {" — "}Receipt {r.payment_receipt_number}, GHS {r.payment_amount}
                  <p className="text-xs text-[var(--ink-soft)]">
                    {r.requested_by_username} requested; {r.decided_by_username} decided on{" "}
                    {r.decided_at && new Date(r.decided_at).toLocaleDateString()}
                  </p>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
    </div>
  );
}
