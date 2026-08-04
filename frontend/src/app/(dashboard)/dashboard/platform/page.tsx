"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api/dashboard";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";
import { KpiTile, SectionCard, FolioLink } from "@/components/dashboard/DashboardVisuals";
import { IconPeople, IconWarning, IconFuneral, IconHome } from "@/components/icons/DashboardIcons";

interface PlatformOverview {
  community_count: number;
  permanent_community_count: number;
  temporary_community_count: number;
  total_members_platform_wide: number;
  total_active_funerals_platform_wide: number;
  pending_announcements_count: number;
  uncontacted_plan_interest_count: number;
  communities: { id: string; name: string; slug: string }[];
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
    { name: "Homepage images", detail: "The rotating photos on the public homepage.", href: "/communities", count: null },
    { name: "Plan interest leads", detail: "Everyone who registered interest in a not-yet-available plan.", href: "/communities", count: overview.uncontacted_plan_interest_count, countLabel: "new" },
    { name: "Announcement review", detail: "Approve, edit, or reject before they reach the notice board.", href: "/communities", count: overview.pending_announcements_count, countLabel: "pending" },
    { name: "Notice Board", detail: "The live, platform-wide board every community sees.", href: "/notice-board", count: null },
  ] : [];

  return (
    <DashboardPageShell folio="Folio X" register="Platform Register" title="Platform Operations" subtitle="Everything needed to run Nsaabodeɛ Smart across every community.">
      {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}

      {overview && (
        <>
          <div className="lg:col-span-2 grid grid-cols-2 gap-px border border-[var(--rule)] bg-[var(--rule)] sm:grid-cols-4">
            <KpiTile label="Permanent" value={overview.permanent_community_count} color="forest" icon={<IconHome />} />
            <KpiTile label="Temporary/rental" value={overview.temporary_community_count} color="violet" icon={<IconHome />} />
            <KpiTile label="Members, platform-wide" value={overview.total_members_platform_wide} color="forest" icon={<IconPeople />} />
            <KpiTile label="Active funerals, platform-wide" value={overview.total_active_funerals_platform_wide} color="clay" icon={<IconFuneral />} />
          </div>

          <SectionCard title="Departments" eyebrow="Every platform-wide tool" accent="violet">
            <ol className="divide-y divide-[var(--rule)]">
              {departments.map((d, i) => (
                <li key={d.name} className="flex items-center justify-between gap-3 py-3">
                  <div className="flex items-baseline gap-3">
                    <span className="font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(2, "0")}</span>
                    <div>
                      <p className="font-medium">{d.name}</p>
                      <p className="text-xs text-[var(--ink-soft)]">{d.detail}</p>
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
            <ol className="divide-y divide-[var(--rule)]">
              {overview.communities.map((c, i) => (
                <li key={c.id} className="flex items-baseline gap-3 py-2">
                  <span className="font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(2, "0")}</span>
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
