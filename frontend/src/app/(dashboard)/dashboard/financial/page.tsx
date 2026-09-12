"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api/dashboard";
import { formatCedis } from "@/lib/formatCedis";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";
import { SectionCard, FolioLink } from "@/components/dashboard/DashboardVisuals";
import { TrendChart } from "@/components/dashboard/TrendChart";
import { ErrorBoundary } from "@/components/ErrorBoundary";

interface FinancialOverview {
  today: { contributions: { total: string }; combined_cash_position_by_method: Record<string, string> };
  month_to_date: { contributions: { total: string } };
  expenses_month_to_date: { total: string };
  outstanding_members: { outstanding_member_count: number };
  collections_trend: { date: string; total: string }[];
  pending_funeral_openings_count: number;
  pending_payment_reversals_count: number;
  // Treasurer and Financial Secretary only — 'Treasurer sees all the financial aspects.'
  pending_reversal_requests?: { id: string; payment__amount: string; reason: string; requested_by__username: string; requested_at: string }[];
  // Auditor only — 'other executives also see what they are capable to,' matched to their actual review-only authority.
  suspicious_transaction_summary?: { unreviewed: number; confirmed: number; dismissed: number };
  recent_reversal_history?: { id: string; payment__amount: string; status: string; reason: string; requested_at: string }[];
  // 'Make it transparent to the community treasurer to have data of those who have paid.'
  paid_members: { member_id: string; member_name: string; total_paid: string; funeral_count: number }[];
}

/** Reconciliation is the actual job here, so the page reads like an open ledger book — money in and money out set side by side as a real spread, not a tile grid — and anything awaiting a decision surfaces as an urgent strip above everything else. */
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
  const todayTotal = methods.reduce((sum, m) => sum + m.value, 0);
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

      <div className="lg:col-span-2 grid divide-y divide-[var(--rule)] border border-[var(--rule)] sm:grid-cols-2 sm:divide-x sm:divide-y-0">
        <div className="p-5">
          <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--forest)]">Money in today</p>
          <p className="font-display mt-2 text-3xl">{formatCedis(overview.today.contributions.total)}</p>
          <p className="mt-1 text-xs text-[var(--ink-soft)]">{formatCedis(overview.month_to_date.contributions.total)} so far this month</p>
        </div>
        <div className="p-5">
          <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--clay-red)]">Money out this month</p>
          <p className="font-display mt-2 text-3xl">{formatCedis(overview.expenses_month_to_date.total)}</p>
          <p className="mt-1 text-xs text-[var(--ink-soft)]">{overview.outstanding_members.outstanding_member_count} members still owing on open funerals</p>
        </div>
      </div>

      <SectionCard title="Reconciliation" eyebrow="By method, today" accent="gold">
        <table className="w-full border-collapse text-sm">
          <tbody>
            {methods.map((m) => (
              <tr key={m.label} className="border-b border-[var(--rule)]">
                <td className="py-2.5 font-mono text-xs uppercase tracking-wide text-[var(--ink-soft)]">{m.label}</td>
                <td className="py-2.5 text-right font-display text-lg">{formatCedis(m.value.toString())}</td>
              </tr>
            ))}
            <tr>
              <td className="pt-2.5 font-mono text-xs font-medium uppercase tracking-wide">Total</td>
              <td className="pt-2.5 text-right font-display text-xl text-[var(--forest)]">{formatCedis(todayTotal.toString())}</td>
            </tr>
          </tbody>
        </table>
      </SectionCard>

      {/* 'Make it transparent to the community treasurer to have data of those who have paid.' */}
      {overview.paid_members.length > 0 && (
        <SectionCard title="Who's paid" eyebrow={`${overview.paid_members.length} member(s) settled on open funerals`} accent="forest">
          <ul className="max-h-72 divide-y divide-[var(--rule)] overflow-y-auto">
            {overview.paid_members.map((m) => (
              <li key={m.member_id} className="flex items-center justify-between py-2 text-sm">
                <span>{m.member_name}</span>
                <span className="font-mono text-xs" style={{ color: "var(--forest)" }}>
                  {formatCedis(m.total_paid)} · {m.funeral_count} funeral(s)
                </span>
              </li>
            ))}
          </ul>
        </SectionCard>
      )}

      {overview.pending_reversal_requests && overview.pending_reversal_requests.length > 0 && (
        <SectionCard title="Reversal requests" eyebrow={`${overview.pending_reversal_requests.length} awaiting a different approver`} accent="clay">
          <ul className="space-y-2">
            {overview.pending_reversal_requests.map((r) => (
              <li key={r.id} className="flex items-center justify-between text-sm">
                <span>
                  {formatCedis(r.payment__amount)} <span className="text-[var(--ink-soft)]">— {r.reason}</span>
                </span>
                <span className="font-mono text-xs text-[var(--ink-soft)]">by {r.requested_by__username}</span>
              </li>
            ))}
          </ul>
          <div className="mt-3"><FolioLink href="/payment-reversals">Open Payment Reversals</FolioLink></div>
        </SectionCard>
      )}

      {overview.suspicious_transaction_summary && (
        <SectionCard title="Under review" eyebrow="What an Auditor actually reviews, not acts on" accent="clay">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <p className="text-xs text-[var(--ink-soft)]">Unreviewed flags</p>
              <p className="font-display text-lg text-[var(--gold)]">{overview.suspicious_transaction_summary.unreviewed}</p>
            </div>
            <div>
              <p className="text-xs text-[var(--ink-soft)]">Confirmed</p>
              <p className="font-display text-lg text-[var(--clay-red)]">{overview.suspicious_transaction_summary.confirmed}</p>
            </div>
            <div>
              <p className="text-xs text-[var(--ink-soft)]">Dismissed</p>
              <p className="font-display text-lg">{overview.suspicious_transaction_summary.dismissed}</p>
            </div>
          </div>
          {overview.recent_reversal_history && overview.recent_reversal_history.length > 0 && (
            <div className="mt-4 border-t border-[var(--rule)] pt-3">
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Recent reversal decisions</p>
              <ul className="mt-2 space-y-1.5">
                {overview.recent_reversal_history.map((r) => (
                  <li key={r.id} className="flex justify-between text-sm">
                    <span>{formatCedis(r.payment__amount)} <span className="text-[var(--ink-soft)]">— {r.reason}</span></span>
                    <span className="font-mono text-xs" style={{ color: r.status === "approved" ? "var(--forest)" : "var(--clay-red)" }}>{r.status}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </SectionCard>
      )}

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
