"use client";

import "@/styles/family-registry-tokens.css";
import Link from "next/link";
import { useExpensesOverview } from "@/lib/hooks/useFuneralLogistics";
import { formatCedis } from "@/lib/formatCedis";
import { KpiTile, FolioLink } from "@/components/dashboard/DashboardVisuals";
import { IconMoney, IconWarning } from "@/components/icons/DashboardIcons";

/**
 * "The funeral expenses should have its own link to be one of the
 * multiple tasks." A real, dedicated entry point — every active
 * funeral's own expense total, in one place, rather than something
 * only reachable by first opening one specific funeral's own detail
 * page. Distinct from Liabilities (outstanding/credit expenses only)
 * — this shows every active funeral's real total regardless of
 * whether it's fully settled.
 */
export default function ExpensesOverviewPage() {
  const { data: overview, isLoading, error } = useExpensesOverview();
  const totalAcrossAllFunerals = overview?.reduce((sum, f) => sum + Number(f.total_expenses), 0) ?? 0;
  const totalOwedAcrossAllFunerals = overview?.reduce((sum, f) => sum + Number(f.total_owed), 0) ?? 0;

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Community Administration</p>
        <h1 className="font-display mt-1 text-4xl">Expenses</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Every currently active funeral&apos;s own expenses, in one place — recording
          an item bought never touches contributions or gifts collected; see each
          funeral&apos;s own page for the full itemized list and the Balance Sheet view.
        </p>
      </header>

      <main className="px-8 py-8">
        <div className="grid grid-cols-2 gap-px border border-[var(--rule)] bg-[var(--rule)] sm:max-w-md">
          <KpiTile label="Total spent, all active funerals" value={formatCedis(String(totalAcrossAllFunerals))} color="clay" icon={<IconMoney />} />
          <KpiTile label="Still owed" value={formatCedis(String(totalOwedAcrossAllFunerals))} color="gold" icon={<IconWarning />} />
        </div>

        <div className="mt-6">
          {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
          {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
          {overview?.length === 0 && (
            <div className="border border-dashed border-[var(--rule)] px-6 py-10 text-center">
              <p className="font-display text-lg">No active funerals right now</p>
            </div>
          )}
          <ol className="divide-y divide-[var(--rule)] border-y-2 border-[var(--ink)]">
            {overview?.map((f, i) => (
              <li key={f.funeral_id} className="flex items-start justify-between gap-3 py-4">
                <div className="flex items-baseline gap-3">
                  <span className="font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(3, "0")}</span>
                  <div>
                    <Link href={`/funerals/${f.funeral_id}`} className="text-sm hover:text-[var(--forest)] hover:underline">
                      {f.deceased_name}
                    </Link>
                    <p className="text-xs text-[var(--ink-soft)]">
                      {f.deceased_family_name} · {f.expense_count} item{f.expense_count === 1 ? "" : "s"} recorded
                      {f.cancelled_count > 0 && ` · ${f.cancelled_count} cancelled`}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-mono text-sm">{formatCedis(f.total_expenses)}</p>
                  {Number(f.total_owed) > 0 && (
                    <p className="text-xs text-[var(--clay-red)]">{formatCedis(f.total_owed)} still owed</p>
                  )}
                </div>
              </li>
            ))}
          </ol>
        </div>

        <div className="mt-6">
          <FolioLink href="/liabilities">View outstanding liabilities only</FolioLink>
        </div>
      </main>
    </div>
  );
}
