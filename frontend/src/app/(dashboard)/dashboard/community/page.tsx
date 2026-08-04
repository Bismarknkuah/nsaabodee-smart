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

interface CommunityOverview {
  active_funerals: number;
  active_member_count: number;
  family_count: number;
  defaulter_count: number;
  today_collections: { contributions: { total: string }; gift_cash?: { total: string } };
  outstanding_members: { outstanding_member_count: number };
  recent_active_funerals: { id: string; deceased_name: string; deceased_family_name: string }[];
  collections_trend: { date: string; total: string }[];
}

/** The busiest role, so the busiest layout — quick actions get their own prominent strip near the top, since this is the page someone acts from all day, not just reads. */
export default function CommunityDashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const overview = data?.sections.community_overview as CommunityOverview | undefined;

  return (
    <DashboardPageShell folio="Folio II" register="Community Register" title="Community Operations" subtitle="Community Admin, Chairman, and Secretary — the full operational picture.">
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

          <div className="lg:col-span-2 flex flex-wrap gap-3 border border-dashed border-[var(--rule)] bg-[var(--surface)] p-4">
            <FolioLink href="/funerals">Manage funerals</FolioLink>
            <FolioLink href="/families">Manage families</FolioLink>
            <FolioLink href="/members">Manage members</FolioLink>
            <FolioLink href="/reports">Reports</FolioLink>
            <FolioLink href="/tasks">Assign a task</FolioLink>
          </div>

          <SectionCard title="Collections" eyebrow="Community-wide, this week" accent="forest">
            <div className="grid grid-cols-2 gap-4">
              <KpiTile
                label={overview.today_collections.gift_cash ? "Collected today" : "Contributions collected today"}
                value={formatCedis((Number(overview.today_collections.contributions.total) + Number(overview.today_collections.gift_cash?.total ?? 0)).toString())}
                color="forest" icon={<IconMoney />}
              />
              <KpiTile label="Owed on open funerals" value={overview.outstanding_members.outstanding_member_count} color="clay" icon={<IconWarning />} />
            </div>
            <ErrorBoundary label="The trend chart">
              <TrendChart data={overview.collections_trend} />
            </ErrorBoundary>
          </SectionCard>

          <SectionCard title="Active funerals" eyebrow={`${overview.recent_active_funerals.length} currently open`} accent="clay">
            {overview.recent_active_funerals.length === 0 ? (
              <p className="text-sm text-[var(--ink-soft)]">No funeral is currently open.</p>
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
          </SectionCard>
        </>
      )}
    </DashboardPageShell>
  );
}
