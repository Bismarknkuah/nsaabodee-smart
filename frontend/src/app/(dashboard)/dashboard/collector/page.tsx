"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { dashboardApi } from "@/lib/api/dashboard";
import { useOfflineSync } from "@/lib/hooks/useOfflineSync";
import { formatCedis } from "@/lib/formatCedis";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";
import { JurisdictionBanner, type Jurisdiction } from "@/components/dashboard/JurisdictionBanner";
import { MyTakingsPanel, type MyTakings } from "@/components/dashboard/TakingsPanels";
import { CollectorActions, HandoverCard, RecentEntries, WorklistTabs, type ChaseRow, type RecentEntry } from "@/components/dashboard/CollectorParts";

import { KpiTile, SectionCard, FolioLink } from "@/components/dashboard/DashboardVisuals";
import { TrendChart } from "@/components/dashboard/TrendChart";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { IconMoney, IconPeople } from "@/components/icons/DashboardIcons";

interface CollectorPerformance {
  jurisdiction?: Jurisdiction;
  my_takings?: (MyTakings & { today_by_method?: Record<string, string>; recent?: RecentEntry[] });
  // Who to chase on funerals still open — inside this collector's own jurisdiction only.
  owing_now?: { members_owing_count: number; total_owed: string; rows: ChaseRow[] };
  // "The collectors at all levels should play the same role as arrears collector."
  arrears?: { members_owing_count: number; total_arrears_outstanding: string; worklist: ChaseRow[] };
  today_performance: { contributions: { total: string; count: number }; combined_cash_position_by_method: Record<string, string> };
  week_performance: { contributions: { total: string; count: number } };
  // "Whole office today" — every collector combined, not just this one.
  whole_office_today: { contributions: { total: string; count: number } };
  customers_owing_count: number;
  active_funerals: { id: string; deceased_name: string; deceased_family_name: string }[];
  collections_trend: { date: string; total: string }[];
  members_to_follow_up: { member_id: string; member_name: string; total_owed: string; funeral_count: number }[];
  // 'Collectors should also have a place in their dashboard where they can see those who have paid and who have not paid.'
  paid_members: { member_id: string; member_name: string; total_paid: string; funeral_count: number }[];
}

export default function CollectorDashboardPage() {
  const router = useRouter();
  const [findQuery, setFindQuery] = useState("");
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const overview = data?.sections.collector_performance as CollectorPerformance | undefined;
  const { online, pendingCount, syncing, drainQueue, refreshQueue } = useOfflineSync();

  const findAccount = (e: React.FormEvent) => {
    e.preventDefault();
    router.push(`/front-desk${findQuery.trim() ? `?q=${encodeURIComponent(findQuery.trim())}` : ""}`);
  };
  const todayTotal = overview?.today_performance.contributions.total ?? "0";

  return (
    <DashboardPageShell folio="Folio IV" register="Collector's Daily Log" title="Collections" subtitle="Take payments, chase what is owed, hand over at day's end — inside your own jurisdiction.">
      {overview && <div className="lg:col-span-2"><JurisdictionBanner jurisdiction={overview.jurisdiction} /></div>}

      <form onSubmit={findAccount} className="lg:col-span-2 flex flex-col gap-3 rounded-[var(--radius)] bg-[var(--card)] p-4 sm:flex-row" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
        <input value={findQuery} onChange={(e) => setFindQuery(e.target.value)} placeholder="Find a member — name, phone, or membership number…" className="flex-1 rounded-lg border border-[var(--border)] px-4 py-3 text-base outline-none focus:border-[var(--primary)]" />
        <button type="submit" className="rounded-lg bg-[var(--forest)] px-6 py-3 text-base font-semibold text-white">Find account</button>
      </form>

      <div className="lg:col-span-2">
        <CollectorActions links={[
          { href: "/front-desk", label: "Front Desk", hint: "Record a payment" },
          { href: "/arrears-desk", label: "Arrears Desk", hint: "Clear old balances, oldest first" },
          { href: "/pending-sync", label: "Pending Sync", hint: `${pendingCount} waiting to upload` },
          { href: "/payment-reversals", label: "Corrections", hint: "Flag or track a wrong entry" },
        ]} />
      </div>

      {/* Offline-first: the same status the whole platform tracks (useOfflineSync), kept visible and compact. */}
      <div className="lg:col-span-2 flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius)] bg-[var(--card)] px-4 py-3" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
        <div className="flex items-center gap-2 font-mono text-xs">
          <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${online ? "bg-[var(--forest)]" : "bg-[var(--clay-red)]"}`} />
          <span className="font-medium">{online ? "Online" : "Offline"}</span>
          <span className="text-[var(--text-soft)]">· {pendingCount} waiting to sync</span>
          {!online && pendingCount > 0 && <span style={{ color: "var(--gold)" }}>· syncs automatically when this device reconnects</span>}
        </div>
        <div className="flex gap-2">
          <button onClick={() => refreshQueue()} className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium hover:border-[var(--primary)]">Refresh</button>
          <button onClick={() => drainQueue()} disabled={!online || syncing || pendingCount === 0} className="rounded-lg bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50">{syncing ? "Syncing…" : "Sync now"}</button>
        </div>
      </div>

      {isLoading && <p className="text-sm text-[var(--text-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
      {overview && (
        <>
          <div className="lg:col-span-2 grid grid-cols-2 gap-4 sm:grid-cols-4">
            <KpiTile label="Collected today" value={formatCedis(todayTotal)} color="forest" icon={<IconMoney />} />
            <KpiTile label="This week" value={formatCedis(overview.week_performance.contributions.total)} color="violet" icon={<IconMoney />} />
            <KpiTile label="Owing now" value={overview.customers_owing_count} color="clay" icon={<IconPeople />} />
            <KpiTile label="In arrears" value={overview.arrears?.members_owing_count ?? 0} color="gold" icon={<IconPeople />} />
          </div>

          <HandoverCard byMethod={overview.my_takings?.today_by_method} total={todayTotal} />
          <SectionCard title="Your pace" eyebrow="Last 7 days" accent="gold">
            <ErrorBoundary label="The trend chart"><TrendChart data={overview.collections_trend} label="Collected" /></ErrorBoundary>
            <p className="mt-2 text-xs text-[var(--text-soft)]">Whole office today: {formatCedis(overview.whole_office_today.contributions.total)}</p>
          </SectionCard>

          <div className="lg:col-span-2"><WorklistTabs owing={overview.owing_now} arrears={overview.arrears} /></div>
          <div className="lg:col-span-2"><RecentEntries rows={overview.my_takings?.recent} /></div>
          <div className="lg:col-span-2"><MyTakingsPanel takings={overview.my_takings} /></div>

          {overview.paid_members.length > 0 && (
            <SectionCard title="Members who've paid" eyebrow={`${overview.paid_members.length} settled`} accent="forest">
              <ol className="divide-y divide-[var(--border-soft)]">
                {overview.paid_members.slice(0, 10).map((m) => (
                  <li key={m.member_id} className="flex items-center justify-between py-2 text-sm"><span>{m.member_name}</span><span className="font-mono text-xs" style={{ color: "var(--forest)" }}>{formatCedis(m.total_paid)}</span></li>
                ))}
              </ol>
            </SectionCard>
          )}
          {overview.active_funerals.length > 0 && (
            <SectionCard title="Funerals you can collect for" eyebrow={`${overview.active_funerals.length} active`} accent="clay">
              <ol className="divide-y divide-[var(--border-soft)]">
                {overview.active_funerals.map((f) => (
                  <li key={f.id} className="py-2 text-sm"><Link href={`/funerals/${f.id}`} className="hover:underline">{f.deceased_name} <span className="text-[var(--text-soft)]">— {f.deceased_family_name}</span></Link></li>
                ))}
              </ol>
            </SectionCard>
          )}
        </>
      )}
    </DashboardPageShell>
  );
}
