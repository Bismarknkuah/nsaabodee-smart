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
import { IconMoney, IconPeople, IconWarning } from "@/components/icons/DashboardIcons";

interface CollectorPerformance {
  today_performance: { contributions: { total: string; count: number }; combined_cash_position_by_method: Record<string, string> };
  week_performance: { contributions: { total: string; count: number } };
  active_funerals: { id: string; deceased_name: string; deceased_family_name: string }[];
  collections_trend: { date: string; total: string }[];
  members_to_follow_up: { member_id: string; member_name: string; total_owed: string; funeral_count: number }[];
}

/** Checked from a phone in the field, so the actions come first — big, thumb-reachable — before any number does. */
export default function CollectorDashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const overview = data?.sections.collector_performance as CollectorPerformance | undefined;

  return (
    <DashboardPageShell folio="Folio IV" register="Collector's Daily Log" title="Today's Collections" subtitle="Your cash position, and the funerals you can collect for.">
      <div className="lg:col-span-2 flex flex-col gap-3 border-2 border-[var(--forest)] bg-white p-4 sm:flex-row">
        <Link href="/front-desk" className="flex-1 bg-[var(--forest)] px-5 py-4 text-center font-display text-lg text-white">
          Open Front Desk
        </Link>
        <Link href="/pending-sync" className="flex-1 border border-[var(--ink)] px-5 py-4 text-center font-display text-lg">
          Pending Sync
        </Link>
      </div>

      {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
      {overview && (
        <>
          <SectionCard title="Today" eyebrow="Your own collections" accent="forest">
            <div className="grid grid-cols-2 gap-4">
              <KpiTile label="Collected" value={formatCedis(overview.today_performance.contributions.total)} color="forest" icon={<IconMoney />} />
              <KpiTile label="Payments" value={overview.today_performance.contributions.count} color="violet" icon={<IconPeople />} />
              <KpiTile label="Cash" value={formatCedis((Number(overview.today_performance.combined_cash_position_by_method?.cash ?? 0)).toString())} color="gold" icon={<IconMoney />} />
              <KpiTile label="MoMo" value={formatCedis((Number(overview.today_performance.combined_cash_position_by_method?.mobile_money ?? 0)).toString())} color="gold" icon={<IconMoney />} />
            </div>
          </SectionCard>

          <SectionCard title="This week" eyebrow="Running total" accent="violet">
            <div className="grid grid-cols-2 gap-4">
              <KpiTile label="Collected" value={formatCedis(overview.week_performance.contributions.total)} color="forest" icon={<IconMoney />} />
              <KpiTile label="Payments" value={overview.week_performance.contributions.count} color="violet" icon={<IconPeople />} />
            </div>
          </SectionCard>

          <SectionCard title="Collection analytics" eyebrow="Your own daily pattern, last 7 days" accent="gold">
            <ErrorBoundary label="The trend chart">
              <TrendChart data={overview.collections_trend} label="Collected" />
            </ErrorBoundary>
          </SectionCard>

          {overview.members_to_follow_up.length > 0 && (
            <SectionCard title="Members to follow up" eyebrow={`${overview.members_to_follow_up.length} with an open balance`} accent="clay">
              <ol className="divide-y divide-[var(--rule)]">
                {overview.members_to_follow_up.map((m, i) => (
                  <li key={m.member_id} className="flex items-center justify-between gap-3 py-2.5">
                    <span className="flex items-baseline gap-3 text-sm">
                      <span className="font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(2, "0")}</span>
                      {m.member_name}
                    </span>
                    <span className="font-mono text-xs text-[var(--clay-red)]">{formatCedis(m.total_owed)}</span>
                  </li>
                ))}
              </ol>
              <div className="mt-4"><FolioLink href="/members">Look up a member</FolioLink></div>
            </SectionCard>
          )}

          {overview.active_funerals.length > 0 && (
            <SectionCard title="Funerals you can collect for" eyebrow={`${overview.active_funerals.length} active`} accent="clay">
              <ol className="divide-y divide-[var(--rule)]">
                {overview.active_funerals.map((f, i) => (
                  <li key={f.id} className="flex items-baseline gap-3 py-2.5">
                    <span className="font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(2, "0")}</span>
                    <Link href={`/funerals/${f.id}`} className="text-sm hover:text-[var(--forest)] hover:underline">
                      {f.deceased_name} <span className="text-[var(--ink-soft)]">— {f.deceased_family_name}</span>
                    </Link>
                  </li>
                ))}
              </ol>
            </SectionCard>
          )}
        </>
      )}
    </DashboardPageShell>
  );
}
