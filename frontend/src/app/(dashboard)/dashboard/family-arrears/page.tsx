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
import { KpiTile, SectionCard, FolioLink } from "@/components/dashboard/DashboardVisuals";
import { TrendChart } from "@/components/dashboard/TrendChart";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { IconMoney, IconPeople } from "@/components/icons/DashboardIcons";

interface FamilyArrearsOfficerPerformance {
  message?: string;
  family_id?: string;
  family_name?: string;
  today_performance?: { contributions: { total: string; count: number }; combined_cash_position_by_method: Record<string, string> };
  week_performance?: { contributions: { total: string; count: number } };
  customers_owing_count?: number;
  collections_trend?: { date: string; total: string }[];
  members_to_follow_up?: { member_id: string; member_name: string; total_owed: string; funeral_count: number }[];
  paid_members?: { member_id: string; member_name: string; total_paid: string; funeral_count: number }[];
}

/**
 * "We have a family arrears collector who is responsible for
 * managing and collecting his family arrears only... each family
 * will have their own family arrears collector." Same shape and
 * conventions as the Collector dashboard this is modeled on, but
 * every number here is already scoped to this one family server-side
 * (dashboard.services._family_arrears_officer_view) — nothing here
 * needs its own family filter, the backend never sends anything
 * beyond this family's own arrears in the first place. The "Find
 * account" search below is likewise already family-scoped, the same
 * fix that closed a real gap in FAMILY_SCOPED_MEMBER_ROLES.
 */
export default function FamilyArrearsOfficerDashboardPage() {
  const router = useRouter();
  const [findQuery, setFindQuery] = useState("");
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const overview = data?.sections.family_arrears_officer_performance as FamilyArrearsOfficerPerformance | undefined;
  const { online, pendingCount, syncing, drainQueue, refreshQueue } = useOfflineSync();

  const findAccount = (e: React.FormEvent) => {
    e.preventDefault();
    router.push(`/front-desk${findQuery.trim() ? `?q=${encodeURIComponent(findQuery.trim())}` : ""}`);
  };

  return (
    <DashboardPageShell
      folio="Folio IV"
      register="Family Arrears Register"
      title={overview?.family_name ? `${overview.family_name}'s Arrears` : "Family Arrears"}
      subtitle="Your family's own closed-funeral arrears — who still owes, and your own collections."
    >
      {overview?.message && <p className="lg:col-span-2 text-sm text-[var(--text-soft)]">{overview.message}</p>}

      {!overview?.message && (
        <>
          <form onSubmit={findAccount} className="lg:col-span-2 flex flex-col gap-3 border-2 border-[var(--forest)] bg-white p-4 sm:flex-row">
            <input
              value={findQuery}
              onChange={(e) => setFindQuery(e.target.value)}
              placeholder="Find a family member — name, phone, or membership number…"
              className="flex-1 rounded-lg border border-[var(--border)] px-4 py-3 text-base outline-none focus:border-[var(--forest)]"
            />
            <button type="submit" className="rounded-lg bg-[var(--forest)] px-6 py-3 font-display text-lg text-white">
              Find account
            </button>
          </form>

          <div className="lg:col-span-2 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/front-desk"
              className="flex-1 rounded-[var(--radius)] bg-[var(--card)] px-5 py-3 text-center font-medium transition-colors hover:border-[var(--primary)]"
              style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}
            >
              Open Front Desk
            </Link>
            <Link
              href="/pending-sync"
              className="flex-1 rounded-[var(--radius)] bg-[var(--card)] px-5 py-3 text-center font-medium transition-colors hover:border-[var(--primary)]"
              style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}
            >
              Pending Sync
            </Link>
          </div>

          <div className="lg:col-span-2 rounded-[var(--radius)] bg-[var(--card)] p-4" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-mono text-xs">
                <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${online ? "bg-[var(--forest)]" : "bg-[var(--clay-red)]"}`} />
                <span className="font-medium">{online ? "Online" : "Offline"}</span>
              </div>
              <div className="flex gap-2">
                <button onClick={() => refreshQueue()} className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium hover:border-[var(--primary)]">
                  Refresh
                </button>
                <button
                  onClick={() => drainQueue()}
                  disabled={!online || syncing || pendingCount === 0}
                  className="rounded-lg bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[var(--forest-hover)] disabled:opacity-50"
                >
                  {syncing ? "Syncing…" : "Sync now"}
                </button>
              </div>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-[var(--border-soft)] bg-[var(--border-soft)] sm:grid-cols-3">
              <KpiTile label="Waiting to sync" value={pendingCount} color={pendingCount > 0 ? "gold" : "forest"} />
              <KpiTile label="Payments taken today" value={overview?.today_performance?.contributions.count ?? 0} color="forest" />
              <KpiTile label="Family members owing" value={overview?.customers_owing_count ?? 0} color="clay" />
            </div>
            {!online && pendingCount > 0 && (
              <p className="mt-3 text-xs" style={{ color: "var(--gold)" }}>
                Still offline — everything above syncs automatically the moment this device reconnects.
              </p>
            )}
          </div>
        </>
      )}

      {isLoading && <p className="text-sm text-[var(--text-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
      {overview && !overview.message && (
        <>
          <div className="rounded-[var(--radius)] bg-[var(--card)] p-5 font-mono text-sm" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
            <p className="text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--text-soft)]">Today&apos;s tape</p>
            <ul className="mt-3 space-y-2 border-t border-dashed border-[var(--border)] pt-3">
              <li className="flex justify-between"><span className="text-[var(--text-soft)]">Payments taken</span><span>{overview.today_performance?.contributions.count ?? 0}</span></li>
              <li className="flex justify-between"><span className="text-[var(--text-soft)]">Cash</span><span>{formatCedis((Number(overview.today_performance?.combined_cash_position_by_method?.cash ?? 0)).toString())}</span></li>
              <li className="flex justify-between"><span className="text-[var(--text-soft)]">Mobile Money</span><span>{formatCedis((Number(overview.today_performance?.combined_cash_position_by_method?.mobile_money ?? 0)).toString())}</span></li>
            </ul>
            <div className="mt-3 flex justify-between border-t border-[var(--border)] pt-3 text-xl font-semibold">
              <span>Total collected</span>
              <span className="text-[var(--forest)]">{formatCedis(overview.today_performance?.contributions.total ?? "0")}</span>
            </div>
          </div>

          <SectionCard title="This week" eyebrow="Running total" accent="violet">
            <div className="grid grid-cols-2 gap-4">
              <KpiTile label="Collected" value={formatCedis(overview.week_performance?.contributions.total ?? "0")} color="forest" icon={<IconMoney />} />
              <KpiTile label="Payments" value={overview.week_performance?.contributions.count ?? 0} color="violet" icon={<IconPeople />} />
            </div>
          </SectionCard>

          <SectionCard title="Collection analytics" eyebrow="Your own daily pattern, last 7 days" accent="gold">
            <ErrorBoundary label="The trend chart">
              <TrendChart data={overview.collections_trend ?? []} label="Collected" />
            </ErrorBoundary>
          </SectionCard>

          {overview.members_to_follow_up && overview.members_to_follow_up.length > 0 && (
            <SectionCard title="Arrears to follow up" eyebrow={`${overview.members_to_follow_up.length} family member(s) with a closed-funeral balance`} accent="clay">
              <ol className="divide-y divide-[var(--border-soft)]">
                {overview.members_to_follow_up.map((m, i) => (
                  <li key={m.member_id} className="flex items-center justify-between gap-3 py-2.5">
                    <span className="flex items-baseline gap-3 text-sm">
                      <span className="font-mono text-xs text-[var(--text-soft)]">{String(i + 1).padStart(2, "0")}</span>
                      {m.member_name}
                    </span>
                    <span className="font-mono text-xs text-[var(--clay-red)]">{formatCedis(m.total_owed)}</span>
                  </li>
                ))}
              </ol>
              <div className="mt-4"><FolioLink href="/front-desk">Collect from a member</FolioLink></div>
            </SectionCard>
          )}

          {overview.paid_members && overview.paid_members.length > 0 && (
            <SectionCard title="Family members who've paid" eyebrow={`${overview.paid_members.length} settled`} accent="forest">
              <ol className="divide-y divide-[var(--border-soft)]">
                {overview.paid_members.map((m, i) => (
                  <li key={m.member_id} className="flex items-center justify-between gap-3 py-2.5">
                    <span className="flex items-baseline gap-3 text-sm">
                      <span className="font-mono text-xs text-[var(--text-soft)]">{String(i + 1).padStart(2, "0")}</span>
                      {m.member_name}
                    </span>
                    <span className="font-mono text-xs" style={{ color: "var(--forest)" }}>{formatCedis(m.total_paid)}</span>
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
