"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { funeralsApi } from "@/lib/api/funerals";
import { formatCedis } from "@/lib/formatCedis";

/**
 * "Each funeral should have its own fund [so] the family knows the
 * expenditure of that particular funeral, so accountability wouldn't
 * be a problem... after every funeral each ledger should know the
 * amount they received, and those who didn't pay." Every number here
 * is already isolated to this one funeral at the database level
 * (funerals.services.funeral_closing_report) — this panel just gives
 * it a clear, dedicated place once the funeral has actually closed,
 * rather than asking someone to read three different screens.
 */
export function ClosingReportPanel({ funeralId }: { funeralId: string }) {
  const [open, setOpen] = useState(false);
  const { data: report, isLoading, error } = useQuery({
    queryKey: ["funeral-closing-report", funeralId],
    queryFn: () => funeralsApi.closingReport(funeralId),
    enabled: open,
  });
  const [downloadError, setDownloadError] = useState<string | null>(null);

  return (
    <section className="mt-6 rounded-[var(--radius)] bg-[var(--card)] p-5" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Closing Report</h2>
          <p className="mt-1 text-sm text-[var(--text-soft)]">
            The amount received, what was spent, and who still owes — for this funeral alone.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setOpen((v) => !v)}
            className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium hover:border-[var(--primary)]"
          >
            {open ? "Hide" : "View report"}
          </button>
          <button
            onClick={() => {
              setDownloadError(null);
              funeralsApi.openClosingReportPdf(funeralId).catch((e) => setDownloadError(e instanceof Error ? e.message : "Could not open the PDF."));
            }}
            className="rounded-lg bg-[var(--forest)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--forest-hover)]"
          >
            Download PDF
          </button>
        </div>
      </div>
      {downloadError && <p className="mt-2 text-xs text-[var(--clay-red)]">{downloadError}</p>}

      {open && (
        <div className="mt-4 border-t border-[var(--border-soft)] pt-4">
          {isLoading && <p className="text-sm text-[var(--text-soft)]">Loading…</p>}
          {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
          {report && (
            <>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                <Figure label="Total received" value={formatCedis(report.total_received)} color="var(--forest)" />
                <Figure label="Still outstanding" value={formatCedis(report.total_outstanding)} color="var(--clay-red)" />
                <Figure label="Spent on logistics" value={formatCedis(report.total_spent_on_logistics)} color="var(--gold)" />
                <Figure label="Total expected" value={formatCedis(report.total_expected)} />
                <Figure label="Gifts received" value={formatCedis(report.total_gifts_received)} color="var(--violet)" />
              </div>

              {/* "After every funeral each ledger should be able to know the amount they received" — each ledger's own figure, not just the merged total above. */}
              <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-[var(--text-soft)]">Amount received, by ledger</h3>
              <ul className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-3">
                <LedgerFigure label="Family Ledger" value={formatCedis(report.ledger_breakdown.family_ledger.collected_total)} />
                <LedgerFigure label="Community Ledger" value={formatCedis(report.ledger_breakdown.community_ledger.collected_total)} />
                <LedgerFigure label="Town Elders Ledger" value={formatCedis(report.ledger_breakdown.town_elders_contribution_ledger.collected_total)} />
                {report.ledger_breakdown.guest_ledger && (
                  <LedgerFigure label="Guest Ledger (gifts)" value={formatCedis(report.ledger_breakdown.guest_ledger.total_value)} />
                )}
                {report.ledger_breakdown.town_leaders_ledger && (
                  <LedgerFigure label="Town Leaders Ledger (gifts)" value={formatCedis(report.ledger_breakdown.town_leaders_ledger.total_value)} />
                )}
                <LedgerFigure label="Asupedeɛ Ledger" value={formatCedis(report.ledger_breakdown.asupede_ledger.collected_total)} />
                <LedgerFigure label="In-Law Ledger" value={formatCedis(report.ledger_breakdown.in_law_ledger.collected_total)} />
              </ul>

              <h3 className="mt-6 text-sm font-semibold uppercase tracking-wide text-[var(--text-soft)]">
                Members who have not yet paid ({report.who_did_not_pay.length})
              </h3>
              {report.who_did_not_pay.length === 0 ? (
                <p className="mt-2 text-sm" style={{ color: "var(--forest)" }}>Everyone obligated on this funeral has paid in full.</p>
              ) : (
                <ul className="mt-2 divide-y divide-[var(--border-soft)]">
                  {report.who_did_not_pay.map((m) => (
                    <li key={m.member_id} className="flex items-center justify-between py-2 text-sm">
                      <div>
                        <p className="font-medium">{m.member_name}</p>
                        <p className="text-xs text-[var(--text-soft)]">{m.family_name}</p>
                      </div>
                      <p className="font-mono text-sm" style={{ color: "var(--clay-red)" }}>{formatCedis(m.balance)}</p>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      )}
    </section>
  );
}

function Figure({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <p className="text-xs text-[var(--text-soft)]">{label}</p>
      <p className="mt-0.5 text-lg font-semibold" style={color ? { color } : undefined}>{value}</p>
    </div>
  );
}

function LedgerFigure({ label, value }: { label: string; value: string }) {
  return (
    <li className="rounded-lg bg-[var(--bg)] p-3">
      <p className="text-xs text-[var(--text-soft)]">{label}</p>
      <p className="mt-0.5 font-mono text-sm font-medium">{value}</p>
    </li>
  );
}
