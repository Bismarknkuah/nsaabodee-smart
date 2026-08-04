"use client";

import { useState } from "react";
import { useFuneralActions } from "@/lib/hooks/useFunerals";
import { formatCedis } from "@/lib/formatCedis";
import { reportsApi } from "@/lib/api/reports";
import { openReceiptPrintWindow } from "@/lib/openReceiptPrintWindow";
import type { ContributionObligation, PaymentMethod } from "@/types/funeral";

export function RecordPaymentDialog({
  funeralId,
  obligation,
  onClose,
}: {
  funeralId: string;
  obligation: ContributionObligation;
  onClose: () => void;
}) {
  const { recordPayment } = useFuneralActions(funeralId);
  const [amount, setAmount] = useState(obligation.balance);
  const [method, setMethod] = useState<PaymentMethod>("cash");
  const [recordedPaymentId, setRecordedPaymentId] = useState<string | null>(null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    recordPayment.mutate(
      { obligationId: obligation.id, amount, method },
      { onSuccess: (payment) => setRecordedPaymentId(payment.id) }
    );
  };

  const printReceipt = async () => {
    if (!recordedPaymentId) return;
    const text = await reportsApi.contributionReceiptText(recordedPaymentId);
    openReceiptPrintWindow(text);
  };

  if (recordedPaymentId) {
    const isCash = method === "cash";
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
        <div className="font-body w-full max-w-sm rounded-sm bg-[var(--surface)] p-6 text-center text-[var(--ink)] shadow-xl">
          <h2 className="font-display text-xl">Payment recorded</h2>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">
            {isCash ? (
              <>Print a receipt for {obligation.member.full_name} now, since this was paid in person.</>
            ) : (
              <>
                No printing needed — {obligation.member.full_name} paid electronically, so their
                receipt is already available in their own &quot;My Receipts&quot; dashboard.
              </>
            )}
          </p>
          <div className="mt-4 flex justify-center gap-2">
            <button onClick={onClose} className="rounded-sm border border-[var(--rule)] px-4 py-2 text-sm">
              Done
            </button>
            <button
              onClick={printReceipt}
              className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white"
            >
              {isCash ? "Print receipt" : "View receipt"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="font-body w-full max-w-sm rounded-sm bg-[var(--surface)] p-6 text-[var(--ink)] shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <h2 className="font-display text-xl">Record payment</h2>
          <button onClick={onClose} className="text-[var(--ink-soft)] hover:text-[var(--ink)]" aria-label="Close">
            ✕
          </button>
        </div>
        <p className="mt-1 text-sm text-[var(--ink-soft)]">
          {obligation.member.full_name} owes {formatCedis(obligation.balance)} of{" "}
          {formatCedis(obligation.expected_amount)} ({obligation.rate_type === "own_family" ? "own family" : "general"} rate).
        </p>

        <form onSubmit={submit} className="mt-4 space-y-4">
          <div>
            <label className="text-sm font-medium">Amount</label>
            <input
              type="number"
              min="0.01"
              step="0.01"
              max={obligation.balance}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
          </div>
          <div>
            <label className="text-sm font-medium">Payment method</label>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value as PaymentMethod)}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            >
              <option value="cash">Cash</option>
              <option value="mobile_money">Mobile Money</option>
              <option value="bank">Bank</option>
              <option value="other">Other</option>
            </select>
          </div>

          {recordPayment.isError && (
            <p className="text-sm text-[var(--clay-red)]">{recordPayment.error.message}</p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-3 py-2 text-sm text-[var(--ink-soft)]">
              Cancel
            </button>
            <button
              type="submit"
              disabled={recordPayment.isPending}
              className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {recordPayment.isPending ? "Recording…" : "Record & issue receipt"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
