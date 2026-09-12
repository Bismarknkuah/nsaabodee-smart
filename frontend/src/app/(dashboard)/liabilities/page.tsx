"use client";

import "@/styles/family-registry-tokens.css";
import Link from "next/link";
import { useLiabilities } from "@/lib/hooks/useFuneralLogistics";
import { formatCedis } from "@/lib/formatCedis";
import { KpiTile } from "@/components/dashboard/DashboardVisuals";
import { IconWarning } from "@/components/icons/DashboardIcons";

const STATUS_LABEL: Record<string, string> = { credit: "Credit (Owed)", partial: "Partially Paid" };

/** "Credit payments create liabilities" — every unsettled expense across the whole community, not just one funeral at a time. */
export default function LiabilitiesPage() {
  const { data: liabilities, isLoading, error } = useLiabilities();
  const totalOwed = liabilities?.reduce((sum, e) => sum + Number(e.balance_owed), 0) ?? 0;

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Community Administration</p>
        <h1 className="font-display mt-1 text-4xl">Liabilities</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Every expense currently owed to a supplier, across every funeral in the community —
          Credit and Partially Paid expenses only. Fully paid or cancelled expenses never appear here.
        </p>
      </header>

      <main className="px-8 py-8">
        <div className="grid grid-cols-2 gap-px border border-[var(--rule)] bg-[var(--rule)] sm:max-w-xs">
          <KpiTile label="Total owed" value={formatCedis(totalOwed.toString())} color="clay" icon={<IconWarning />} />
          <KpiTile label="Open items" value={liabilities?.length ?? 0} color="gold" />
        </div>

        <div className="mt-6">
          {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
          {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
          {liabilities?.length === 0 && (
            <div className="border border-dashed border-[var(--rule)] px-6 py-10 text-center">
              <p className="font-display text-lg">Nothing owed right now</p>
            </div>
          )}
          <ol className="divide-y divide-[var(--rule)] border-y-2 border-[var(--ink)]">
            {liabilities?.map((e, i) => (
              <li key={e.id} className="flex items-start justify-between gap-3 py-4">
                <div className="flex items-baseline gap-3">
                  <span className="font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(3, "0")}</span>
                  <div>
                    <Link href={`/funerals/${e.funeral_event}`} className="text-sm hover:text-[var(--forest)] hover:underline">
                      {e.item_name || e.description}
                    </Link>
                    <p className="text-xs text-[var(--ink-soft)]">
                      {e.supplier_name || "No supplier recorded"} · {STATUS_LABEL[e.status] ?? e.status} · {e.voucher_number}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-mono text-sm text-[var(--clay-red)]">{formatCedis(e.balance_owed)}</p>
                  <p className="text-xs text-[var(--ink-soft)]">of {formatCedis(e.amount)}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </main>
    </div>
  );
}
