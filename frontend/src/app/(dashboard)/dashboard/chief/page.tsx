"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { dashboardApi } from "@/lib/api/dashboard";
import { formatCedis } from "@/lib/formatCedis";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";
import { KpiTile, SectionCard, FolioLink } from "@/components/dashboard/DashboardVisuals";
import { TrendChart } from "@/components/dashboard/TrendChart";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { IconMoney, IconPeople, IconWarning, IconFuneral, IconHome } from "@/components/icons/DashboardIcons";

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
}

/** Oversight, not operations — the layout stays deliberately quiet: a strategic KPI strip, a trend, a register of what's active, and the announcements a chief would want relayed. No action buttons; this is a page for reading, not doing. Outstanding contributions and welfare-fund figures are deliberately aggregate-only — never a member's own name or personal debt, matching "must not access sensitive personal financial information unless explicitly authorized." */
export default function ChiefDashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const overview = data?.sections.traditional_leader_overview as TraditionalLeaderOverview | undefined;

  return (
    <DashboardPageShell folio="Folio I" register="Chief's Register" title="Community Oversight" subtitle="A strategic view of the community's standing — for reading, not for operating.">
      {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
      {overview && (
        <>
          <div className="lg:col-span-2 grid grid-cols-2 gap-px border border-[var(--rule)] bg-[var(--rule)] sm:grid-cols-4">
            <KpiTile label="Active funerals" value={overview.active_funerals} color="clay" icon={<IconFuneral />} />
            <KpiTile label="Active members" value={overview.active_member_count} color="forest" icon={<IconPeople />} />
            <KpiTile label="Families" value={overview.family_count} color="violet" icon={<IconHome />} />
            <KpiTile label="Defaulters" value={overview.defaulter_count} color="gold" icon={<IconWarning />} />
          </div>

          <SectionCard title="Contribution register" eyebrow="This week's pattern" accent="forest">
            <div className="grid grid-cols-2 gap-4">
              <KpiTile label="Contributed today" value={formatCedis(overview.today_collections.contributions.total)} color="forest" icon={<IconMoney />} />
              <KpiTile label="Still owed, community-wide" value={formatCedis(overview.outstanding_summary.total_owed)} color="clay" icon={<IconWarning />} />
            </div>
            <p className="mt-2 text-xs text-[var(--ink-soft)]">{overview.outstanding_summary.member_count} member(s) currently owe money on an open funeral.</p>
            <ErrorBoundary label="The trend chart">
              <TrendChart data={overview.collections_trend} label="Contributions" />
            </ErrorBoundary>
            <p className="mt-4 text-xs italic text-[var(--ink-soft)]">
              Donation, gift, and individual member debt detail stay private — the same restraint
              the finance committee itself observes. Only aggregate figures appear here.
            </p>
          </SectionCard>

          <SectionCard title="Community welfare funds" eyebrow="Every family fund, aggregated" accent="violet">
            <div className="grid grid-cols-3 gap-3">
              <KpiTile label="Active funds" value={overview.welfare_fund_summary.active_fund_count} color="violet" icon={<IconHome />} />
              <KpiTile label="Contributing families" value={overview.welfare_fund_summary.contributing_family_count} color="forest" />
              <KpiTile label="Total ever contributed" value={formatCedis(overview.welfare_fund_summary.total_contributions_ever)} color="gold" icon={<IconMoney />} />
            </div>
          </SectionCard>

          <SectionCard title="Executive activity" eyebrow="This month, in aggregate" accent="gold">
            <div className="grid grid-cols-3 gap-3">
              <KpiTile label="Contributions recorded" value={overview.executive_performance_summary.payments_recorded_this_month} color="forest" />
              <KpiTile label="Gifts recorded" value={overview.executive_performance_summary.gifts_recorded_this_month} color="violet" />
              <KpiTile label="Active collectors" value={overview.executive_performance_summary.active_collector_count} color="gold" icon={<IconPeople />} />
            </div>
          </SectionCard>

          <SectionCard title="Audit summary" eyebrow={`Last ${overview.audit_summary.period_days} days`} accent="clay">
            <p className="text-sm">{overview.audit_summary.total_events} governance action(s) logged.</p>
            {Object.keys(overview.audit_summary.by_category).length > 0 && (
              <ul className="mt-2 space-y-1">
                {Object.entries(overview.audit_summary.by_category).map(([category, count]) => (
                  <li key={category} className="flex justify-between text-xs text-[var(--ink-soft)]">
                    <span className="capitalize">{category.replace(/_/g, " ")}</span>
                    <span className="font-mono">{count}</span>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>

          <SectionCard title="Active funerals" eyebrow={`${overview.recent_active_funerals.length} currently open`} accent="clay">
            {overview.recent_active_funerals.length === 0 ? (
              <p className="text-sm text-[var(--ink-soft)]">No funeral is currently open in the community.</p>
            ) : (
              <ol className="divide-y divide-[var(--rule)]">
                {overview.recent_active_funerals.map((f, i) => (
                  <li key={f.id} className="flex items-baseline gap-3 py-2.5">
                    <span className="font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(2, "0")}</span>
                    <Link href={`/funerals/${f.id}`} className="text-sm hover:text-[var(--forest)] hover:underline">
                      {f.deceased_name} <span className="text-[var(--ink-soft)]">— {f.deceased_family_name}</span>
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
