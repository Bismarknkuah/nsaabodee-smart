"use client";

import { useState } from "react";
import { useFinancialOverview } from "@/lib/hooks/useFuneralLogistics";
import { formatCedis } from "@/lib/formatCedis";

type ViewMode = "balance_sheet" | "money_received" | "expenses";

/**
 * 'They can only record items which has been bought without deducting
 * it from money received, can also record money received separately,
 * and should have an option to merge the money received and the items
 * bought to balance the sheet.' The underlying ledgers were already
 * always separate (see funeral_financial_overview's own docstring —
 * this never merges anything, it only sums totals that already exist
 * independently). What was missing was making that separateness, and
 * the merge, into a real, deliberate choice rather than one fixed
 * strip always showing the combined figure. Three explicit views:
 * "Money In" and "Expenses" each show only their own side, with zero
 * reference to the other — genuinely independent, not just visually
 * separated — and "Balance Sheet" is the one place the two are
 * deliberately brought together, on request.
 */
export function FinancialOverviewStrip({ funeralId }: { funeralId: string }) {
  const { data } = useFinancialOverview(funeralId);
  const [view, setView] = useState<ViewMode>("balance_sheet");
  if (!data) return null;

  const net = Number(data.net_cash_position);
  const moneyIn = Number(data.contributions_collected) + Number(data.gift_cash_collected);

  return (
    <div className="mt-6 rounded-sm border border-[var(--rule)] bg-white p-4">
      <div className="flex gap-1 rounded-full bg-[var(--surface)] p-1 text-xs">
        {([
          ["balance_sheet", "Balance Sheet"],
          ["money_received", "Money Received"],
          ["expenses", "Expenses"],
        ] as [ViewMode, string][]).map(([mode, label]) => (
          <button
            key={mode}
            onClick={() => setView(mode)}
            className={`flex-1 rounded-full px-3 py-1.5 font-medium transition-colors ${
              view === mode ? "bg-[var(--ink)] text-white" : "text-[var(--ink-soft)] hover:text-[var(--ink)]"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {view === "balance_sheet" && (
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Contributions in" value={formatCedis(data.contributions_collected)} tone="forest" />
          <Stat label="Gift cash in" value={formatCedis(data.gift_cash_collected)} tone="violet" />
          <Stat label="Expenses out" value={formatCedis(data.total_expenses)} tone="clay-red" />
          <Stat label="Net cash position" value={formatCedis(data.net_cash_position)} tone={net >= 0 ? "forest" : "clay-red"} emphasize />
        </div>
      )}

      {view === "money_received" && (
        <div className="mt-4">
          <p className="text-xs text-[var(--ink-soft)]">Every cedi that has come in — no expense figure enters this view at all.</p>
          <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Stat label="Contributions in" value={formatCedis(data.contributions_collected)} tone="forest" />
            <Stat label="Gift cash in" value={formatCedis(data.gift_cash_collected)} tone="violet" />
            <Stat label="Total money in" value={formatCedis(String(moneyIn))} tone="forest" emphasize />
          </div>
          {Number(data.gift_estimated_item_value) > 0 && (
            <p className="mt-2 text-xs text-[var(--ink-soft)]">
              Plus {formatCedis(data.gift_estimated_item_value)} in gifted items (not cash, not counted above).
            </p>
          )}
        </div>
      )}

      {view === "expenses" && (
        <div className="mt-4">
          <p className="text-xs text-[var(--ink-soft)]">Every purchase recorded — nothing here is deducted from money received automatically.</p>
          <div className="mt-3">
            <Stat label="Total spent" value={formatCedis(data.total_expenses)} tone="clay-red" emphasize />
          </div>
        </div>
      )}
    </div>
  );
}

function Stat({
  label,
  value,
  tone,
  emphasize = false,
}: {
  label: string;
  value: string;
  tone: "forest" | "violet" | "clay-red";
  emphasize?: boolean;
}) {
  const color = { forest: "var(--forest)", violet: "var(--violet)", "clay-red": "var(--clay-red)" }[tone];
  return (
    <div>
      <p className="text-xs text-[var(--ink-soft)]">{label}</p>
      <p className={`font-mono ${emphasize ? "text-lg font-semibold" : "text-base font-medium"}`} style={{ color }}>
        {value}
      </p>
    </div>
  );
}
