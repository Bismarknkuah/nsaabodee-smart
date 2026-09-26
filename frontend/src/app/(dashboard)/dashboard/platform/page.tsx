"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api/dashboard";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";
import { KpiTile, SectionCard, FolioLink } from "@/components/dashboard/DashboardVisuals";
import Link from "next/link";
import { formatCedis } from "@/lib/formatCedis";
import { IconPeople, IconWarning, IconFuneral, IconHome, IconMoney } from "@/components/icons/DashboardIcons";

interface PlatformOverview {
  community_count: number;
  permanent_community_count: number;
  temporary_community_count: number;
  total_members_platform_wide: number;
  total_active_funerals_platform_wide: number;
  pending_announcements_count: number;
  uncontacted_plan_interest_count: number;
  communities_needing_subscription_attention_count: number;
  unpaid_billing_total: string;
  unpaid_billing_count: number;
  open_support_ticket_count: number;
  communities: { id: string; name: string; slug: string }[];
  // The reference console layout: KPI tiles, subscriptions by status, communities by plan, recent registrations.
  total_users_platform_wide: number;
  subscription_revenue_total: string;
  subscriptions_by_status: { active: number; expired: number; suspended: number };
  communities_by_plan: { plan_code: string; plan_name: string; community_count: number }[];
  recent_registrations: { id: string; name: string; slug: string; is_active: boolean; created_at: string; subscription_plan__name: string | null }[];
}

/**
 * "The platform admin should also have more features to help the
 * platform admin manage all the communities and other services." An
 * operations-center layout — a numbered directory of every tool this
 * role actually uses, each row showing its own live count, so nothing
 * that needs attention stays invisible.
 */
export default function PlatformDashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const overview = data?.sections.platform_overview as PlatformOverview | undefined;

  const departments = overview ? [
    { name: "Communities", detail: "Onboard, extend access, deactivate, payout accounts, billing.", href: "/communities", count: overview.community_count, countLabel: "active" },
    { name: "Subscriptions & billing", detail: "Communities with unpaid fees or expiring access — send a reminder directly.", href: "/communities", count: overview.communities_needing_subscription_attention_count, countLabel: "need attention" },
    { name: "Homepage images", detail: "The rotating photos on the public homepage.", href: "/communities", count: null },
    { name: "Plan interest leads", detail: "Everyone who registered interest in a not-yet-available plan.", href: "/communities", count: overview.uncontacted_plan_interest_count, countLabel: "new" },
    { name: "Announcement review", detail: "Approve, edit, or reject before they reach the notice board.", href: "/communities", count: overview.pending_announcements_count, countLabel: "pending" },
    { name: "Notice Board", detail: "The live, platform-wide board every community sees.", href: "/notice-board", count: null },
    { name: "Support queue", detail: "Tickets submitted by any community, waiting on a response.", href: "/support-queue", count: overview.open_support_ticket_count, countLabel: "open" },
    { name: "Revenue", detail: "Platform-wide billing totals across every community.", href: "/revenue", count: null },
    { name: "Feature flags", detail: "Platform-wide kill-switches for individual features.", href: "/system-settings", count: null },
    { name: "User management", detail: "Community Admin accounts across every community — reset passwords, manage access.", href: "/user-management", count: null },
  ] : [];

  return (
    <DashboardPageShell folio="Folio X" register="Platform Register" title="Platform Operations" subtitle="Everything needed to run Nsaabodeɛ Smart across every community.">
      {isLoading && <p className="text-sm text-[var(--text-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}

      {overview && (
        <>
          {/*
            "The platform admin dashboard should also look like [the
            reference] template." KPI tiles across the top, then
            subscriptions by status, communities by plan, and recent
            registrations side by side — the same shape as the
            reference console.
          */}
          <div className="lg:col-span-2 grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-5">
            <KpiTile label="Communities" value={overview.community_count} color="forest" icon={<IconHome />} />
            <KpiTile label="Members" value={overview.total_members_platform_wide} color="forest" icon={<IconPeople />} />
            <KpiTile label="Users" value={overview.total_users_platform_wide} color="violet" icon={<IconPeople />} />
            <KpiTile label="Subscription revenue" value={formatCedis(overview.subscription_revenue_total)} color="gold" icon={<IconMoney />} />
            <KpiTile label="Active funerals" value={overview.total_active_funerals_platform_wide} color="clay" icon={<IconFuneral />} />
          </div>
          <p className="lg:col-span-2 -mt-3 text-xs text-[var(--text-soft)]">
            {overview.permanent_community_count} permanent · {overview.temporary_community_count} temporary/rental · {overview.unpaid_billing_count} pending invoice{overview.unpaid_billing_count === 1 ? "" : "s"} ({formatCedis(overview.unpaid_billing_total)})
          </p>

          <SectionCard title="Subscriptions by status" eyebrow="Every community, by access state" accent="forest">
            <StatusBars status={overview.subscriptions_by_status} />
          </SectionCard>

          <SectionCard title="Communities by plan" eyebrow="How many are on each tier" accent="violet">
            <PlanBars rows={overview.communities_by_plan} />
            <div className="mt-3"><FolioLink href="/plans">Manage plans</FolioLink></div>
          </SectionCard>

          <SectionCard title="Recent registrations" eyebrow="Newest communities first" accent="gold">
            <ul className="divide-y divide-[var(--border-soft)]">
              {overview.recent_registrations.map((c) => (
                <li key={c.id} className="flex items-center justify-between gap-3 py-2.5">
                  <div>
                    <Link href="/communities" className="text-sm font-medium hover:underline">{c.name}</Link>
                    <p className="text-xs text-[var(--text-soft)]">{c.subscription_plan__name ?? "No plan"} · {new Date(c.created_at).toLocaleDateString(undefined, { dateStyle: "medium" })}</p>
                  </div>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${c.is_active ? "bg-[var(--forest-soft)] text-[var(--forest)]" : "bg-[var(--clay-red-soft)] text-[var(--clay-red)]"}`}>
                    {c.is_active ? "Active" : "Suspended"}
                  </span>
                </li>
              ))}
              {overview.recent_registrations.length === 0 && <li className="py-2 text-xs text-[var(--text-soft)]">No communities yet.</li>}
            </ul>
          </SectionCard>

          <SectionCard title="Departments" eyebrow="Every platform-wide tool" accent="violet">
            <ol className="divide-y divide-[var(--border-soft)]">
              {departments.map((d, i) => (
                <li key={d.name} className="flex items-center justify-between gap-3 py-3">
                  <div className="flex items-baseline gap-3">
                    <span className="font-mono text-xs text-[var(--text-soft)]">{String(i + 1).padStart(2, "0")}</span>
                    <div>
                      <p className="font-medium">{d.name}</p>
                      <p className="text-xs text-[var(--text-soft)]">{d.detail}</p>
                    </div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {d.count !== null && d.count > 0 && (
                      <span
                        className="rounded-full px-2 py-0.5 text-xs font-medium"
                        style={
                          d.countLabel === "pending"
                            ? { backgroundColor: "var(--clay-red-soft)", color: "var(--clay-red)" }
                            : { backgroundColor: "var(--gold-soft)", color: "var(--gold)" }
                        }
                      >
                        {d.count} {d.countLabel}
                      </span>
                    )}
                    <FolioLink href={d.href}>Open</FolioLink>
                  </div>
                </li>
              ))}
            </ol>
          </SectionCard>

          <SectionCard title="Active communities" eyebrow={`${overview.communities.length} listed`} accent="gold">
            <ol className="divide-y divide-[var(--border-soft)]">
              {overview.communities.map((c, i) => (
                <li key={c.id} className="flex items-baseline gap-3 py-2">
                  <span className="font-mono text-xs text-[var(--text-soft)]">{String(i + 1).padStart(2, "0")}</span>
                  <span className="text-sm">{c.name}</span>
                </li>
              ))}
            </ol>
          </SectionCard>
        </>
      )}
    </DashboardPageShell>
  );
}


/** Horizontal bars, no chart library — three statuses is too few to justify one. */
function StatusBars({ status }: { status: { active: number; expired: number; suspended: number } }) {
  const rows: [string, number, string][] = [["Active", status.active, "var(--forest)"], ["Expired", status.expired, "var(--gold)"], ["Suspended", status.suspended, "var(--clay-red)"]];
  const total = rows.reduce((a, [, n]) => a + n, 0) || 1;
  return (
    <ul className="space-y-3">
      {rows.map(([label, n, color]) => (
        <li key={label}>
          <div className="flex justify-between text-sm"><span>{label}</span><span className="font-mono text-xs text-[var(--text-soft)]">{n}</span></div>
          <div className="mt-1 h-2 overflow-hidden rounded-full bg-[var(--bg)]"><div className="h-full rounded-full" style={{ width: `${(n / total) * 100}%`, backgroundColor: color }} /></div>
        </li>
      ))}
    </ul>
  );
}

function PlanBars({ rows }: { rows: { plan_code: string; plan_name: string; community_count: number }[] }) {
  const max = Math.max(1, ...rows.map((r) => r.community_count));
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r.plan_code}>
          <div className="flex justify-between text-sm"><span>{r.plan_name}</span><span className="font-mono text-xs text-[var(--text-soft)]">{r.community_count}</span></div>
          <div className="mt-1 h-2 overflow-hidden rounded-full bg-[var(--bg)]"><div className="h-full rounded-full bg-[var(--primary)]" style={{ width: `${(r.community_count / max) * 100}%` }} /></div>
        </li>
      ))}
      {rows.length === 0 && <li className="text-xs text-[var(--text-soft)]">No plans defined yet.</li>}
    </ul>
  );
}
