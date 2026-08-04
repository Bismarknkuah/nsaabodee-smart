"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { dashboardApi } from "@/lib/api/dashboard";
import { formatCedis } from "@/lib/formatCedis";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";
import { SectionCard, FolioLink } from "@/components/dashboard/DashboardVisuals";
import { MyOutstandingObligationsCard } from "@/components/dashboard/MyOutstandingObligationsCard";

interface MemberOverview {
  membership_number?: string;
  defaulter_tier?: string;
  missed_contributions_count?: number;
  active_funerals?: { id: string; deceased_name: string; deceased_family_name: string }[];
  message?: string;
  donations_received?: { total_received: string; donation_count: number } | null;
  family_info?: { family_id: string; family_name: string; family_head_name: string | null; family_secretary_name: string | null; family_treasurer_name: string | null } | null;
  upcoming_meetings?: { id: string; title: string; scheduled_for: string; location: string; family_id: string | null }[];
  welfare_obligations?: { id: string; campaign__title: string; campaign__category__name: string; expected_amount: string; amount_paid: string }[];
}
interface CommitteePositionOverview {
  funeral_id: string;
  deceased_name: string;
  your_title: string;
  task_summary: { total: number; done: number; pending_approval: number };
  contribution_summary: { total_expected?: string; total_collected?: string };
  attendance_count: number;
  upcoming_meetings: { id: string; title: string; scheduled_for: string; location: string }[];
}

/** Quieter than any other dashboard on purpose — this is one person looking up their own entry in the register, not running operations. Single column, generous space, no dense tile grid. */
export default function MemberDashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const overview = data?.sections.member_overview as MemberOverview | undefined;
  const inGoodStanding = overview?.defaulter_tier === "none";
  const committeePositions = data?.sections.committee_positions as CommitteePositionOverview[] | undefined;

  return (
    <DashboardPageShell folio="Folio VI" register="Membership Record" title="Your Standing" subtitle="Your account, your receipts, and what's happening in your community.">
      {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}

      {overview && (
        <div className="lg:col-span-2 mx-auto w-full max-w-xl">
          {overview.message && <p className="text-center text-sm text-[var(--ink-soft)]">{overview.message}</p>}
          {overview.membership_number && (
            <div className="border-2 p-8 text-center" style={{ borderColor: inGoodStanding ? "var(--forest)" : "var(--clay-red)" }}>
              <p className="font-mono text-xs uppercase tracking-[0.16em] text-[var(--ink-soft)]">{overview.membership_number}</p>
              <p className="font-display mt-3 text-2xl" style={{ color: inGoodStanding ? "var(--forest)" : "var(--clay-red)" }}>
                {inGoodStanding ? "In good standing" : `${overview.defaulter_tier?.replace(/_/g, " ")}`}
              </p>
              {!inGoodStanding && (
                <p className="mt-1 text-sm text-[var(--ink-soft)]">{overview.missed_contributions_count} missed contribution(s)</p>
              )}

              <div className="mt-6 flex flex-wrap justify-center gap-3">
                <FolioLink href="/my-receipts">My receipts</FolioLink>
                {overview.donations_received !== null && overview.donations_received !== undefined && (
                  <FolioLink href="/my-donations-received">Donations given in my name</FolioLink>
                )}
              </div>
            </div>
          )}

          {overview.active_funerals && overview.active_funerals.length > 0 && (
            <div className="mt-6">
              <SectionCard title="Active funerals in your community" accent="clay">
                <ul className="divide-y divide-[var(--rule)]">
                  {overview.active_funerals.map((f) => (
                    <li key={f.id} className="py-2 text-sm">
                      <Link href={`/funerals/${f.id}`} className="hover:text-[var(--forest)] hover:underline">
                        {f.deceased_name} <span className="text-[var(--ink-soft)]">— {f.deceased_family_name}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </SectionCard>
            </div>
          )}

          {overview.family_info && (
            <div className="mt-6">
              <SectionCard title="Your family" eyebrow={overview.family_info.family_name} accent="violet">
                <ul className="space-y-1 text-sm">
                  {overview.family_info.family_head_name && <li>Family Head: {overview.family_info.family_head_name}</li>}
                  {overview.family_info.family_secretary_name && <li>Family Secretary: {overview.family_info.family_secretary_name}</li>}
                  {overview.family_info.family_treasurer_name && <li>Family Treasurer: {overview.family_info.family_treasurer_name}</li>}
                </ul>
                <div className="mt-3"><FolioLink href={`/family-fund/${overview.family_info.family_id}`}>Family fund</FolioLink></div>
              </SectionCard>
            </div>
          )}

          {overview.upcoming_meetings && overview.upcoming_meetings.length > 0 && (
            <div className="mt-6">
              <SectionCard title="Meeting invitations" accent="forest">
                <ul className="space-y-3">
                  {overview.upcoming_meetings.map((m) => (
                    <li key={m.id} className="border-l-2 border-[var(--forest)] pl-3">
                      <p className="text-sm font-medium">
                        {m.title}
                        {!m.family_id && <span className="ml-2 text-xs text-[var(--ink-soft)]">(community-wide)</span>}
                      </p>
                      <p className="text-xs text-[var(--ink-soft)]">
                        {new Date(m.scheduled_for).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                        {m.location && ` · ${m.location}`}
                      </p>
                    </li>
                  ))}
                </ul>
              </SectionCard>
            </div>
          )}

          {overview.welfare_obligations && overview.welfare_obligations.length > 0 && (
            <div className="mt-6">
              <SectionCard title="Welfare & contributions" eyebrow="Beyond funerals" accent="gold">
                <ul className="divide-y divide-[var(--rule)]">
                  {overview.welfare_obligations.map((o) => (
                    <li key={o.id} className="flex items-center justify-between py-2 text-sm">
                      <div>
                        <p>{o.campaign__title}</p>
                        <p className="text-xs text-[var(--ink-soft)]">{o.campaign__category__name}</p>
                      </div>
                      <span className="font-mono text-xs">
                        {formatCedis(o.amount_paid)} / {formatCedis(o.expected_amount)}
                      </span>
                    </li>
                  ))}
                </ul>
                <div className="mt-3"><FolioLink href="/welfare-contributions">Open Welfare & Contributions</FolioLink></div>
              </SectionCard>
            </div>
          )}

          {committeePositions && committeePositions.length > 0 && (
            <div className="mt-6 space-y-4">
              {committeePositions.map((p) => (
                <SectionCard key={p.funeral_id} title={p.your_title} eyebrow={`${p.deceased_name}'s funeral committee`} accent="violet">
                  <div className="grid grid-cols-3 gap-3 text-sm">
                    <div>
                      <p className="text-xs text-[var(--ink-soft)]">Tasks</p>
                      <p className="font-display text-lg">{p.task_summary.done}/{p.task_summary.total}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[var(--ink-soft)]">Attendance</p>
                      <p className="font-display text-lg">{p.attendance_count}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[var(--ink-soft)]">Pending approval</p>
                      <p className="font-display text-lg">{p.task_summary.pending_approval}</p>
                    </div>
                  </div>
                  {p.upcoming_meetings.length > 0 && (
                    <ul className="mt-3 space-y-1 border-t border-[var(--rule)] pt-3">
                      {p.upcoming_meetings.map((m) => (
                        <li key={m.id} className="text-xs text-[var(--ink-soft)]">
                          {m.title} — {new Date(m.scheduled_for).toLocaleDateString()}
                        </li>
                      ))}
                    </ul>
                  )}
                  <div className="mt-3"><FolioLink href={`/funerals/${p.funeral_id}`}>Open this funeral</FolioLink></div>
                </SectionCard>
              ))}
            </div>
          )}
        </div>
      )}
      <div className="lg:col-span-2 mx-auto w-full max-w-xl">
        <MyOutstandingObligationsCard />
      </div>
    </DashboardPageShell>
  );
}
