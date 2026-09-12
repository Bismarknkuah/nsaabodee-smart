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
import { usePendingDeskAssignments, useApproveDeskAssignment } from "@/lib/hooks/useFunerals";
import { usePendingBereavedRepApprovals, useApproveBereavedRep } from "@/lib/hooks/useFamilies";
import { useAuthStore } from "@/store/authStore";

interface CommunityOverview {
  active_funerals: number;
  active_member_count: number;
  family_count: number;
  defaulter_count: number;
  today_collections: { contributions: { total: string }; gift_cash?: { total: string } };
  outstanding_members: { outstanding_member_count: number };
  recent_active_funerals: { id: string; deceased_name: string; deceased_family_name: string }[];
  collections_trend: { date: string; total: string }[];
  task_summary?: { pending: number; in_progress: number; pending_approval: number; done: number; overdue: number };
}

/**
 * The busiest, most reactive role on the platform — so the layout
 * itself is a triage desk, not a report. Whatever genuinely needs
 * this person's own decision today leads the page, ahead of any
 * static number; the KPI count becomes a compact status strip instead
 * of the first thing on the page, since a Community Admin checking in
 * mid-morning wants "what's waiting on me" before "how many members
 * do we have."
 */
export default function CommunityDashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const overview = data?.sections.community_overview as CommunityOverview | undefined;
  const currentUser = useAuthStore((s) => s.user);
  const isCommunityAdmin = currentUser?.role === "community_admin";
  const isBereavedRepApprover = Boolean(currentUser?.role && ["community_admin", "chairman", "secretary"].includes(currentUser.role));
  const { data: pendingDeskAssignments } = usePendingDeskAssignments(isCommunityAdmin);
  const approveDeskAssignment = useApproveDeskAssignment();
  const { data: pendingBereavedReps } = usePendingBereavedRepApprovals(isBereavedRepApprover);
  const approveBereavedRep = useApproveBereavedRep();

  const pendingCount = (pendingDeskAssignments?.length ?? 0) + (pendingBereavedReps?.length ?? 0);

  return (
    <DashboardPageShell folio="Folio II" register="Community Register" title="Community Operations" subtitle="Community Admin, Chairman, and Secretary — the full operational picture.">
      {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
      {overview && (
        <>
          {pendingCount > 0 && (
            <div className="lg:col-span-2 border-2 border-[var(--gold)] bg-[var(--gold-soft)] p-4">
              <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--gold)]">
                Awaits your action: {pendingCount} item{pendingCount === 1 ? "" : "s"}
              </p>
              <ul className="mt-3 divide-y divide-[var(--rule)]">
                {pendingDeskAssignments?.map((a) => (
                  <li key={a.id} className="flex items-center justify-between gap-3 py-2">
                    <span className="text-sm">
                      Desk assignment: {a.username} <span className="text-[var(--ink-soft)]">, {a.deceased_name}&apos;s funeral</span>
                    </span>
                    <button
                      onClick={() => approveDeskAssignment.mutate(a.id)}
                      disabled={approveDeskAssignment.isPending}
                      className="shrink-0 rounded-sm border border-[var(--forest)] bg-white px-2 py-1 text-xs text-[var(--forest)] disabled:opacity-50"
                    >
                      Approve
                    </button>
                  </li>
                ))}
                {pendingBereavedReps?.map((a) => (
                  <li key={a.id} className="flex items-center justify-between gap-3 py-2">
                    <span className="text-sm">
                      Deceased Rep: {a.username} <span className="text-[var(--ink-soft)]">, represents {a.family_name}</span>
                    </span>
                    <button
                      onClick={() => approveBereavedRep.mutate(a.id)}
                      disabled={approveBereavedRep.isPending}
                      className="shrink-0 rounded-sm border border-[var(--forest)] bg-white px-2 py-1 text-xs text-[var(--forest)] disabled:opacity-50"
                    >
                      Approve
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="lg:col-span-2 flex flex-wrap items-center gap-x-6 gap-y-2 border-y border-[var(--rule)] py-3 font-mono text-sm">
            <span><strong className="text-[var(--clay-red)]">{overview.active_funerals}</strong> active funerals</span>
            <span className="text-[var(--rule)]">·</span>
            <span><strong className="text-[var(--forest)]">{overview.active_member_count}</strong> members</span>
            <span className="text-[var(--rule)]">·</span>
            <span><strong className="text-[var(--violet)]">{overview.family_count}</strong> families</span>
            <span className="text-[var(--rule)]">·</span>
            <span><strong className="text-[var(--gold)]">{overview.defaulter_count}</strong> defaulters</span>
          </div>

          <div className="lg:col-span-2 flex flex-wrap gap-3 border border-dashed border-[var(--rule)] bg-[var(--surface)] p-4">
            <FolioLink href="/funerals">Manage funerals</FolioLink>
            <FolioLink href="/families">Manage families</FolioLink>
            <FolioLink href="/members">Manage members</FolioLink>
            <FolioLink href="/reports">Reports</FolioLink>
            <FolioLink href="/tasks">Assign a task</FolioLink>
          </div>

          <div className="grid gap-4 lg:col-span-2 lg:grid-cols-2">
            {overview.task_summary && (
            <SectionCard title="Task oversight" eyebrow="Every task assigned community-wide" accent="violet">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                <div>
                  <p className="text-xs text-[var(--ink-soft)]">Pending</p>
                  <p className="font-display text-lg">{overview.task_summary.pending}</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--ink-soft)]">In progress</p>
                  <p className="font-display text-lg">{overview.task_summary.in_progress}</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--ink-soft)]">Awaiting approval</p>
                  <p className="font-display text-lg text-[var(--gold)]">{overview.task_summary.pending_approval}</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--ink-soft)]">Done</p>
                  <p className="font-display text-lg" style={{ color: "var(--forest)" }}>{overview.task_summary.done}</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--ink-soft)]">Overdue</p>
                  <p className="font-display text-lg text-[var(--clay-red)]">{overview.task_summary.overdue}</p>
                </div>
              </div>
              <div className="mt-3"><FolioLink href="/tasks">Open Tasks</FolioLink></div>
            </SectionCard>
            )}

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
          </div>
        </>
      )}
    </DashboardPageShell>
  );
}
