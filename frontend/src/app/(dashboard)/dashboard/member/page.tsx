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
  my_tasks?: { id: string; title: string; status: string; due_date: string | null; funeral_event__deceased_name: string | null }[];
  my_desk_assignments?: { funeral_event_id: string; funeral_event__deceased_name: string; desk_type: string }[];
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
        <div className="lg:col-span-2 mx-auto w-full max-w-xl space-y-6">
          {overview.message && <p className="text-center text-sm text-[var(--ink-soft)]">{overview.message}</p>}

          {/* Identity — who you are in this register, first and clearest */}
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

          {/* What needs your attention — a real balance to pay is the single most actionable thing here */}
          <MyOutstandingObligationsCard />

          {overview.my_tasks && overview.my_tasks.length > 0 && (
            <SectionCard title="Your tasks" eyebrow="Assigned to you" accent="clay">
              <ul className="divide-y divide-[var(--rule)]">
                {overview.my_tasks.map((t) => (
                  <li key={t.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                    <div>
                      <p>{t.title}</p>
                      {t.funeral_event__deceased_name && (
                        <p className="text-xs text-[var(--ink-soft)]">{t.funeral_event__deceased_name}&apos;s funeral</p>
                      )}
                    </div>
                    <div className="text-right">
                      <span className="rounded-sm bg-[var(--surface)] px-2 py-0.5 text-xs capitalize text-[var(--ink-soft)]">
                        {t.status.replace(/_/g, " ")}
                      </span>
                      {t.due_date && <p className="mt-1 text-xs text-[var(--ink-soft)]">Due {new Date(t.due_date).toLocaleDateString()}</p>}
                    </div>
                  </li>
                ))}
              </ul>
              <div className="mt-3"><FolioLink href="/tasks">Open Tasks</FolioLink></div>
            </SectionCard>
          )}

          {overview.my_desk_assignments && overview.my_desk_assignments.length > 0 && (
            <SectionCard title="Your desk assignments" eyebrow="Real, working desk access">
              <ul className="space-y-1.5 text-sm">
                {overview.my_desk_assignments.map((a) => (
                  <li key={a.funeral_event_id}>
                    <Link href={`/front-desk`} className="hover:text-[var(--forest)] hover:underline">
                      {a.desk_type.charAt(0).toUpperCase() + a.desk_type.slice(1)} desk
                    </Link>{" "}
                    <span className="text-[var(--ink-soft)]">for {a.funeral_event__deceased_name}&apos;s funeral</span>
                  </li>
                ))}
              </ul>
            </SectionCard>
          )}

          {committeePositions && committeePositions.length > 0 && (
            <div className="space-y-4">
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
                          {m.title}, {new Date(m.scheduled_for).toLocaleDateString()}
                        </li>
                      ))}
                    </ul>
                  )}
                  <div className="mt-3"><FolioLink href={`/funerals/${p.funeral_id}`}>Open this funeral</FolioLink></div>
                </SectionCard>
              ))}
            </div>
          )}

          {overview.upcoming_meetings && overview.upcoming_meetings.length > 0 && (
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
          )}

          {overview.family_info && (
            <SectionCard title="Your family" eyebrow={overview.family_info.family_name} accent="violet">
              <ul className="space-y-1 text-sm">
                {overview.family_info.family_head_name && <li>Family Head: {overview.family_info.family_head_name}</li>}
                {overview.family_info.family_secretary_name && <li>Family Secretary: {overview.family_info.family_secretary_name}</li>}
                {overview.family_info.family_treasurer_name && <li>Family Treasurer: {overview.family_info.family_treasurer_name}</li>}
              </ul>
              <div className="mt-3"><FolioLink href={`/family-fund/${overview.family_info.family_id}`}>Family fund</FolioLink></div>
            </SectionCard>
          )}

          {overview.active_funerals && overview.active_funerals.length > 0 && (
            <SectionCard title="Active funerals in your community" accent="clay">
              <ul className="divide-y divide-[var(--rule)]">
                {overview.active_funerals.map((f) => (
                  <li key={f.id} className="py-2 text-sm">
                    <Link href={`/funerals/${f.id}`} className="hover:text-[var(--forest)] hover:underline">
                      {f.deceased_name} <span className="text-[var(--ink-soft)]">, {f.deceased_family_name}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </SectionCard>
          )}

          {overview.welfare_obligations && overview.welfare_obligations.length > 0 && (
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
          )}
        </div>
      )}
    </DashboardPageShell>
  );
}
