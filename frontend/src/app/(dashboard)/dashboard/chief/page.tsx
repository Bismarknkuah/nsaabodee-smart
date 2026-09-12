"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { dashboardApi } from "@/lib/api/dashboard";
import { formatCedis } from "@/lib/formatCedis";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";
import { SectionCard, FolioLink } from "@/components/dashboard/DashboardVisuals";
import { TrendChart } from "@/components/dashboard/TrendChart";
import { ErrorBoundary } from "@/components/ErrorBoundary";

interface TraditionalLeaderOverview {
  active_funerals: number;
  active_member_count: number;
  family_count: number;
  defaulter_count: number;
  today_collections: { contributions: { total: string } };
  outstanding_summary: { member_count: number; total_owed: string };
  recent_active_funerals: { id: string; deceased_name: string; deceased_family_name: string }[];
  collections_trend: { date: string; total: string }[];
  recent_announcements: { id: string; title: string; submitted_at: string }[];
  welfare_fund_summary: { active_fund_count: number; total_contributions_ever: string; contributing_family_count: number };
  executive_performance_summary: { payments_recorded_this_month: number; gifts_recorded_this_month: number; active_collector_count: number };
  audit_summary: { period_days: number; total_events: number; by_category: Record<string, number> };
  upcoming_meetings: { id: string; title: string; scheduled_for: string; location: string }[];
  family_compliance_comparison: { family_name: string; member_obligation_count: number; paid_count: number; compliance_rate: number }[];
  growth_trend: { month: string; active_member_count: number }[];
  task_summary?: { pending: number; in_progress: number; pending_approval: number; done: number; overdue: number };
}

/** Oversight, not operations — so the page reads like a chronicle written for the Chief, not a data dashboard: numbers woven into prose the way a real briefing would state them, not scattered across tile grids. No action buttons; this is a page for reading, not doing. Outstanding contributions and welfare-fund figures are deliberately aggregate-only — never a member's own name or personal debt, matching "must not access sensitive personal financial information unless explicitly authorized." */
export default function ChiefDashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const overview = data?.sections.traditional_leader_overview as TraditionalLeaderOverview | undefined;

  return (
    <DashboardPageShell folio="Folio I" register="Chief's Register" title="Community Oversight" subtitle="A strategic view of the community's standing, for reading, not for operating.">
      {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
      {overview && (
        <>
          <div className="lg:col-span-2 border border-[var(--rule)] bg-white p-6">
            <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">The standing of the community</p>
            <p className="font-display mt-3 text-xl leading-relaxed">
              {overview.active_member_count} members across {overview.family_count} families,{" "}
              {overview.defaulter_count > 0 ? `${overview.defaulter_count} presently in arrears` : "none presently in arrears"}.{" "}
              {overview.active_funerals > 0
                ? `${overview.active_funerals} funeral${overview.active_funerals > 1 ? "s are" : " is"} currently open, together owed ${formatCedis(overview.outstanding_summary.total_owed)} from ${overview.outstanding_summary.member_count} member(s).`
                : "No funeral is currently open."}{" "}
              {formatCedis(overview.today_collections.contributions.total)} was contributed today.
            </p>
            <p className="mt-4 text-xs italic text-[var(--ink-soft)]">
              Donation, gift, and individual member debt detail stay private, the same restraint the
              finance committee itself observes. Only aggregate figures ever appear here.
            </p>
            <ErrorBoundary label="The trend chart">
              <TrendChart data={overview.collections_trend} label="Contributions" />
            </ErrorBoundary>
          </div>

          <div className="grid gap-4 lg:col-span-2 lg:grid-cols-2">
            <SectionCard title="Welfare, beyond funerals" eyebrow="Every family fund, aggregated" accent="violet">
              <p className="text-sm leading-relaxed">
                {overview.welfare_fund_summary.active_fund_count} active fund(s), drawing from{" "}
                {overview.welfare_fund_summary.contributing_family_count} contributing famil{overview.welfare_fund_summary.contributing_family_count === 1 ? "y" : "ies"}.
                {" "}{formatCedis(overview.welfare_fund_summary.total_contributions_ever)} has been contributed in total, ever.
              </p>
            </SectionCard>

            <SectionCard title="The executive committee's work" eyebrow="This month, in aggregate" accent="gold">
              <p className="text-sm leading-relaxed">
                {overview.executive_performance_summary.payments_recorded_this_month} contribution(s) and{" "}
                {overview.executive_performance_summary.gifts_recorded_this_month} gift(s) recorded, by{" "}
                {overview.executive_performance_summary.active_collector_count} active collector(s).{" "}
                {overview.audit_summary.total_events} governance action(s) logged in the last {overview.audit_summary.period_days} days.
                {overview.task_summary && (
                  <>
                    {" "}Of {overview.task_summary.pending + overview.task_summary.in_progress + overview.task_summary.pending_approval + overview.task_summary.done} task(s)
                    assigned community-wide, {overview.task_summary.done} are done
                    {overview.task_summary.overdue > 0 && <span className="text-[var(--clay-red)]"> and {overview.task_summary.overdue} are overdue</span>}.
                  </>
                )}
              </p>
            </SectionCard>
          </div>

          <div className="grid gap-4 lg:col-span-2 lg:grid-cols-2">
            <SectionCard title="Family compliance" eyebrow="On currently open funerals, worst to best" accent="clay">
              {overview.family_compliance_comparison.length === 0 ? (
                <p className="text-sm text-[var(--ink-soft)]">No family has an open obligation right now.</p>
              ) : (
                <ul className="space-y-2.5">
                  {overview.family_compliance_comparison.map((f) => (
                    <li key={f.family_name}>
                      <div className="flex items-baseline justify-between text-sm">
                        <span>{f.family_name}</span>
                        <span className="font-mono text-xs text-[var(--ink-soft)]">
                          {f.paid_count}/{f.member_obligation_count} paid
                        </span>
                      </div>
                      <div className="mt-1 h-1.5 w-full bg-[var(--rule)]">
                        <div
                          className="h-1.5"
                          style={{
                            width: `${f.compliance_rate}%`,
                            backgroundColor: f.compliance_rate >= 75 ? "var(--forest)" : f.compliance_rate >= 40 ? "var(--gold)" : "var(--clay-red)",
                          }}
                        />
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </SectionCard>

            <SectionCard title="Community growth" eyebrow="Active members, last 6 months" accent="forest">
              <div className="flex items-end gap-2" style={{ height: "80px" }}>
                {(() => {
                  const max = Math.max(...overview.growth_trend.map((r) => r.active_member_count), 1);
                  return overview.growth_trend.map((r) => (
                    <div key={r.month} className="flex flex-1 flex-col items-center gap-1">
                      <div
                        className="w-full bg-[var(--forest)]"
                        style={{ height: `${Math.max((r.active_member_count / max) * 64, 2)}px` }}
                        title={`${r.month}: ${r.active_member_count} members`}
                      />
                      <span className="font-mono text-[9px] text-[var(--ink-soft)]">
                        {new Date(`${r.month}-01`).toLocaleDateString(undefined, { month: "short" })}
                      </span>
                    </div>
                  ));
                })()}
              </div>
              <p className="mt-2 text-xs text-[var(--ink-soft)]">
                {overview.growth_trend[overview.growth_trend.length - 1]?.active_member_count ?? 0} active members today.
              </p>
            </SectionCard>
          </div>

          <SectionCard title="Active funerals" eyebrow={`${overview.recent_active_funerals.length} currently open`} accent="clay">
            {overview.recent_active_funerals.length === 0 ? (
              <p className="text-sm text-[var(--ink-soft)]">No funeral is currently open in the community.</p>
            ) : (
              <ol className="divide-y divide-[var(--rule)]">
                {overview.recent_active_funerals.map((f, i) => (
                  <li key={f.id} className="flex items-baseline gap-3 py-2.5">
                    <span className="font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(2, "0")}</span>
                    <Link href={`/funerals/${f.id}`} className="text-sm hover:text-[var(--forest)] hover:underline">
                      {f.deceased_name} <span className="text-[var(--ink-soft)]">, {f.deceased_family_name}</span>
                    </Link>
                  </li>
                ))}
              </ol>
            )}
            <div className="mt-4"><FolioLink href="/reports">Open full reports</FolioLink></div>
          </SectionCard>

          {overview.upcoming_meetings.length > 0 && (
            <SectionCard title="Meeting schedule" eyebrow="Upcoming" accent="forest">
              <ul className="space-y-3">
                {overview.upcoming_meetings.map((m) => (
                  <li key={m.id} className="border-l-2 border-[var(--forest)] pl-3">
                    <p className="text-sm font-medium">{m.title}</p>
                    <p className="text-xs text-[var(--ink-soft)]">
                      {new Date(m.scheduled_for).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                      {m.location && ` · ${m.location}`}
                    </p>
                  </li>
                ))}
              </ul>
            </SectionCard>
          )}

          {overview.recent_announcements.length > 0 && (
            <SectionCard title="Announcements" eyebrow="From the notice board" accent="gold">
              <ul className="space-y-3">
                {overview.recent_announcements.map((a) => (
                  <li key={a.id} className="border-l-2 border-[var(--gold)] pl-3">
                    <p className="font-display text-base italic">&ldquo;{a.title}&rdquo;</p>
                  </li>
                ))}
              </ul>
              <div className="mt-4"><FolioLink href="/notice-board">Open Notice Board</FolioLink></div>
            </SectionCard>
          )}
        </>
      )}
    </DashboardPageShell>
  );
}
