"use client";

import { useState } from "react";
import { useGiftDonations, useGiftDonationsReconciliation, useGiftSummary, useGiftCategoryBreakdown } from "@/lib/hooks/useGifts";
import { formatCedis } from "@/lib/formatCedis";
import { RecordGiftDialog } from "./RecordGiftDialog";
import { PayGiftViaMomoDialog } from "./PayGiftViaMomoDialog";
import { DonationAccountsPanel } from "./DonationAccountsPanel";
import { giftsApi } from "@/lib/api/gifts";
import type { DonorCategory } from "@/types/gift";

const CATEGORY_LABEL: Record<DonorCategory, string> = {
  guest: "Guests",
  town_leader: "Town Leaders",
  other: "Other",
};

export function GiftLedgerPanel({ funeralId }: { funeralId: string }) {
  const [category, setCategory] = useState<DonorCategory | undefined>(undefined);
  const { data: donations, isLoading, isError } = useGiftDonations(funeralId, category);
  const { data: summary } = useGiftSummary(funeralId);
  const { data: categoryBreakdown } = useGiftCategoryBreakdown(funeralId);
  const [showRecord, setShowRecord] = useState(false);
  const [showMomo, setShowMomo] = useState(false);
  const [reconciliationReason, setReconciliationReason] = useState<string | null>(null);
  const { data: reconciliationDonations } = useGiftDonationsReconciliation(funeralId, reconciliationReason ?? "");
  const isAnonymized = !reconciliationReason && donations?.some((d) => d.donor_name.startsWith("Donor #"));
  const displayedDonations = reconciliationReason ? reconciliationDonations : donations;

  return (
    <section className="mt-10 rounded-sm border-2 border-[var(--violet)] bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-widest text-[var(--violet)]">Ledger 2 — separate from contributions</p>
          <h2 className="font-display mt-1 text-xl" style={{ color: "var(--violet)" }}>Gift Donations</h2>
          <p className="mt-1 max-w-xl text-sm text-[var(--ink-soft)]">
            Voluntary gifts from anyone — a donor doesn&apos;t need to be a registered
            member, and can give any amount they choose. Never counted toward, or affected
            by, the mandatory contribution ledger above.
          </p>
        </div>
        <button
          onClick={() => setShowRecord(true)}
          className="shrink-0 rounded-sm px-4 py-2 text-sm font-medium text-white hover:opacity-90"
          style={{ backgroundColor: "var(--violet)" }}
        >
          Record a gift
        </button>
      </div>
      <div className="mt-2 flex justify-end">
        <button
          onClick={() => setShowMomo(true)}
          className="rounded-sm border px-3 py-1.5 text-xs font-medium hover:opacity-80"
          style={{ borderColor: "var(--violet)", color: "var(--violet)" }}
        >
          Or: pay via MoMo instead
        </button>
      </div>

      <div className="mt-4">
        <DonationAccountsPanel funeralId={funeralId} />
      </div>

      {isAnonymized && (
        <div className="mt-3 flex items-center justify-between gap-3 rounded-sm border border-dashed p-3 text-xs" style={{ borderColor: "var(--gold)", backgroundColor: "var(--gold-soft, transparent)" }}>
          {reconciliationReason ? (
            <>
              <span style={{ color: "var(--clay-red)" }}>Viewing real donor names — this access was just logged for: &ldquo;{reconciliationReason}&rdquo;</span>
              <button onClick={() => setReconciliationReason(null)} className="shrink-0 underline">Go back to anonymized view</button>
            </>
          ) : (
            <>
              <span className="text-[var(--ink-soft)]">
                Donor names are anonymized for this temporary event. Real names are only shown for reconciliation, auditing, or legal compliance.
              </span>
              <button
                onClick={() => {
                  const reason = window.prompt("Reason for viewing real donor names (reconciliation, auditing, or legal compliance):");
                  if (reason && reason.trim()) setReconciliationReason(reason.trim());
                }}
                className="shrink-0 rounded-sm border px-3 py-1 font-medium hover:opacity-80"
                style={{ borderColor: "var(--violet)", color: "var(--violet)" }}
              >
                Reveal for reconciliation
              </button>
            </>
          )}
        </div>
      )}

      {isError ? (
        <div className="mt-4 rounded-sm border border-dashed border-[var(--rule)] p-4 text-sm text-[var(--ink-soft)]">
          The detailed gift ledger and totals are only visible to this family&apos;s own
          head or a community administrator — the rest of the funeral committee sees the
          mandatory contribution ledger only. You can still record a gift above.
        </div>
      ) : (
        <>
          {categoryBreakdown && (
            <div className="mt-4 grid grid-cols-3 gap-3 rounded-sm p-3 text-center text-sm" style={{ backgroundColor: "var(--violet-soft)" }}>
              {(Object.entries(categoryBreakdown.by_category) as [DonorCategory, { donor_count: number; total_value: string }][]).map(
                ([cat, bucket]) => (
                  <div key={cat}>
                    <p className="text-xs text-[var(--ink-soft)]">{CATEGORY_LABEL[cat]}</p>
                    <p className="font-mono text-lg font-medium">{formatCedis(bucket.total_value)}</p>
                    <p className="text-xs text-[var(--ink-soft)]">{bucket.donor_count} donor{bucket.donor_count === 1 ? "" : "s"}</p>
                  </div>
                )
              )}
            </div>
          )}

          {summary && (
            <div className="mt-3 flex items-center justify-center gap-6 text-xs text-[var(--ink-soft)]">
              <span>{summary.donation_count} total donations</span>
              <span>{formatCedis(summary.total_combined_value)} combined value</span>
              <button
                onClick={() => giftsApi.openAllReceiversStatementPdf(funeralId)}
                className="rounded-full border border-[var(--rule)] px-3 py-1 font-medium hover:border-[var(--violet)]"
                style={{ color: "var(--violet)" }}
              >
                Print every receiver&apos;s statement
              </button>
            </div>
          )}

          <div className="mt-4 flex gap-1 rounded-full bg-[var(--surface)] p-1 text-xs">
            {([undefined, "guest", "town_leader", "other"] as (DonorCategory | undefined)[]).map((c) => (
              <button
                key={c ?? "all"}
                onClick={() => setCategory(c)}
                className={`rounded-full px-3 py-1.5 font-medium ${category === c ? "bg-[var(--ink)] text-white" : "text-[var(--ink-soft)]"}`}
              >
                {c ? CATEGORY_LABEL[c] : "All"}
              </button>
            ))}
          </div>

          <div className="mt-3 overflow-hidden rounded-sm border border-[var(--rule)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--rule)] text-left text-xs uppercase tracking-wide text-[var(--ink-soft)]">
                  <th className="px-4 py-2">Donor</th>
                  <th className="px-4 py-2">For</th>
                  <th className="px-4 py-2">Gift</th>
                  <th className="px-4 py-2 text-right">Value</th>
                  <th className="px-4 py-2">Receipt</th>
                </tr>
              </thead>
              <tbody>
                {isLoading && (
                  <tr><td colSpan={5} className="px-4 py-6 text-center text-[var(--ink-soft)]">Loading gift ledger…</td></tr>
                )}
                {!isLoading && displayedDonations?.length === 0 && (
                  <tr><td colSpan={5} className="px-4 py-6 text-center text-[var(--ink-soft)]">No gifts recorded yet.</td></tr>
                )}
                {displayedDonations?.map((d) => (
                  <tr key={d.id} className="border-b border-[var(--rule)] last:border-b-0">
                    <td className="px-4 py-2 font-medium">
                      {d.donor_name}
                      {d.donor_hometown && <span className="ml-1 text-xs text-[var(--ink-soft)]">({d.donor_hometown})</span>}
                    </td>
                    <td className="px-4 py-2 text-xs text-[var(--ink-soft)]">
                      {d.received_by_member_name ? (
                        <>
                          {d.received_by_member_name}
                          {d.relationship_to_recipient && ` (${d.relationship_to_recipient})`}
                        </>
                      ) : (
                        d.connected_relative_name || "—"
                      )}
                    </td>
                    <td className="px-4 py-2 text-[var(--ink-soft)]">
                      {[d.amount_cash !== "0.00" && formatCedis(d.amount_cash), d.gift_item].filter(Boolean).join(" + ") || "—"}
                    </td>
                    <td className="px-4 py-2 text-right font-mono">{formatCedis(d.total_value)}</td>
                    <td className="px-4 py-2 font-mono text-xs text-[var(--ink-soft)]">{d.receipt_number}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {showRecord && <RecordGiftDialog funeralId={funeralId} onClose={() => setShowRecord(false)} />}
      {showMomo && <PayGiftViaMomoDialog funeralId={funeralId} onClose={() => setShowMomo(false)} />}
    </section>
  );
}
