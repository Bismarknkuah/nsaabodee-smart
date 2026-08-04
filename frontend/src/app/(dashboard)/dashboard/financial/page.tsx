"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api/dashboard";
import { formatCedis } from "@/lib/formatCedis";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";
import { KpiTile, SectionCard, FolioLink } from "@/components/dashboard/DashboardVisuals";
import { TrendChart } from "@/components/dashboard/TrendChart";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { IconMoney, IconPeople, IconWarning } from "@/components/icons/DashboardIcons";

interface FinancialOverview {
  today: { contributions: { total: string }; combined_cash_position_by_method: Record<string, string> };
  month_to_date: { contributions: { total: string } };
  expenses_month_to_date: { total: string };
  outstanding_members: { outstanding_member_count: number };
  collections_trend: { date: string; total: string }[];
  pending_funeral_openings_count: number;
  pending_payment_reversals_count: number;
}

/** Reconciliation is the actual job here, so the cash/MoMo/bank split is a literal ledger table, not a tile grid — and anything awaiting a decision surfaces as an urgent strip above everything else. */
export default function FinancialDashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const overview = data?.sections.financial_overview as FinancialOverview | undefined;

  if (!overview) {
    return (
      <DashboardPageShell folio="Folio III" register="Financial Register" title="Financial Oversight" subtitle="Treasurer, Financial Secretary, and Auditor.">
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
        {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
      </DashboardPageShell>
    );
  }

  const methods = [
    { label: "Cash", value: Number(overview.today.combined_cash_position_by_method?.cash ?? 0) },
    { label: "Mobile Money", value: Number(overview.today.combined_cash_position_by_method?.mobile_money ?? 0) },
    { label: "Bank", value: Number(overview.today.combined_cash_position_by_method?.bank ?? 0) },
  ];
  const hasPending = overview.pending_funeral_openings_count > 0 || overview.pending_payment_reversals_count > 0;

  return (
    <DashboardPageShell folio="Folio III" register="Financial Register" title="Financial Oversight" subtitle="Treasurer, Financial Secretary, and Auditor — reconciliation and approvals.">
      {hasPending && (
        <div className="lg:col-span-2 flex flex-wrap items-center gap-3 border-2 border-[var(--clay-red)] bg-[var(--clay-red-soft)] p-4">
          <span className="font-mono text-[11px] font-medium uppercase tracking-wide text-[var(--clay-red)]">Awaiting your decision —</span>
          {overview.pending_funeral_openings_count > 0 && (
            <FolioLink href="/funerals" tone="urgent">{overview.pending_funeral_openings_count} funeral opening{overview.pending_funeral_openings_count > 1 ? "s" : ""}</FolioLink>
          )}
          {overview.pending_payment_reversals_count > 0 && (
            <FolioLink href="/payment-reversals" tone="urgent">{overview.pending_payment_reversals_count} payment reversal{overview.pending_payment_reversals_count > 1 ? "s" : ""}</FolioLink>
          )}
        </div>
      )}

      <div className="lg:col-span-2 grid grid-cols-2 gap-px border border-[var(--rule)] bg-[var(--rule)] sm:grid-cols-4">
        <KpiTile label="Contributions today" value={formatCedis(overview.today.contributions.total)} color="forest" icon={<IconMoney />} />
        <KpiTile label="Contributions this month" value={formatCedis(overview.month_to_date.contributions.total)} color="forest" icon={<IconMoney />} />
        <KpiTile label="Expenses this month" value={formatCedis(overview.expenses_month_to_date.total)} color="clay" icon={<IconWarning />} />
        <KpiTile label="Members still owing" value={overview.outstanding_members.outstanding_member_count} color="gold" icon={<IconPeople />} />
      </div>

      <SectionCard title="Reconciliation" eyebrow="By method, today" accent="gold">
        <table className="w-full border-collapse text-sm">
          <tbody>
            {methods.map((m) => (
              <tr key={m.label} className="border-b border-[var(--rule)] last:border-0">
                <td className="py-2.5 font-mono text-xs uppercase tracking-wide text-[var(--ink-soft)]">{m.label}</td>
                <td className="py-2.5 text-right font-display text-lg">{formatCedis(m.value.toString())}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </SectionCard>

      <SectionCard title="Contribution trend" eyebrow="Community-wide, this week" accent="forest">
        <ErrorBoundary label="The trend chart">
          <TrendChart data={overview.collections_trend} label="Contributions" />
        </ErrorBoundary>
        <div className="mt-4 flex flex-wrap gap-3">
          <FolioLink href="/reports">Open full reports</FolioLink>
          <FolioLink href="/suspicious-transactions">Suspicious transactions</FolioLink>
        </div>
      </SectionCard>
    </DashboardPageShell>
  );
}
