"use client";

import "@/styles/family-registry-tokens.css";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { reportsApi } from "@/lib/api/reports";
import { formatCedis } from "@/lib/formatCedis";

/**
 * 'All receipt printed should have the QR scanner so when they scan
 * it should confirm the amount they paid and who received the pay, I
 * mean the collector.' This is exactly what a printed receipt's own
 * QR code opens — a plain, immediate confirmation, not a login screen
 * demanding an explanation of what they're even looking at.
 */
export default function VerifyReceiptPage() {
  const { id } = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["verify-receipt", id],
    queryFn: () => reportsApi.verifyReceipt(id),
    enabled: Boolean(id),
  });

  return (
    <div className="font-body flex min-h-screen items-center justify-center bg-[var(--paper)] px-6 text-[var(--ink)]">
      <div className="w-full max-w-sm border-2 border-[var(--ink)] bg-white p-6 text-center">
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Checking receipt…</p>}
        {error && (
          <>
            <p className="font-display text-2xl text-[var(--clay-red)]">Not verified</p>
            <p className="mt-2 text-sm text-[var(--ink-soft)]">{(error as Error).message}</p>
          </>
        )}
        {data && (
          <>
            <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em]" style={{ color: "var(--forest)" }}>
              Receipt Verified
            </p>
            <p className="font-display mt-2 text-4xl" style={{ color: "var(--forest)" }}>{formatCedis(data.amount)}</p>
            <p className="mt-1 text-xs text-[var(--ink-soft)]">Receipt {data.receipt_number}</p>

            <dl className="mt-6 space-y-2 border-t border-[var(--rule)] pt-4 text-left text-sm">
              <div className="flex justify-between">
                <dt className="text-[var(--ink-soft)]">Paid by</dt>
                <dd className="font-medium">{data.member_name}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[var(--ink-soft)]">Received by (collector)</dt>
                <dd className="font-medium">{data.collector_name || "—"}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[var(--ink-soft)]">For</dt>
                <dd className="font-medium">{data.deceased_name}&apos;s funeral</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[var(--ink-soft)]">Method</dt>
                <dd className="font-medium capitalize">{data.method.replace("_", " ")}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-[var(--ink-soft)]">When</dt>
                <dd className="font-medium">{new Date(data.paid_at).toLocaleString()}</dd>
              </div>
            </dl>
          </>
        )}
      </div>
    </div>
  );
}
