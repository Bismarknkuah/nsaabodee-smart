"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api/dashboard";
import type { MemberRegistryAnalytics } from "@/lib/api/members";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";
import { KpiTile, SectionCard, FolioLink } from "@/components/dashboard/DashboardVisuals";
import { RegistryAnalyticsView } from "@/components/members/RegistryAnalyticsView";
import { IconPeople } from "@/components/icons/DashboardIcons";

interface RegistrationOverview {
  registry: MemberRegistryAnalytics;
  my_registrations_total: number;
  my_registrations_this_month: number;
  registers_town_elders_only: boolean;
}

/**
 * "The registration officer is not allowed to see the financial
 * oversight; his responsibility is to manage the community's
 * information." Member information only — who is registered, by
 * what breakdown, and what this officer has registered. No
 * collections, no ledgers, no expenses anywhere on this page.
 */
export default function RegistrationDashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const overview = data?.sections?.registration_overview as RegistrationOverview | undefined;
  const scope = overview?.registry.scope;
  const scopeLabel = scope === "family" ? "Your family's register" : scope === "town_elders" ? "Town Elders register" : "Community register";

  return (
    <DashboardPageShell folio="Folio VI" register={scopeLabel} title="Registration" subtitle={overview?.registers_town_elders_only ? "You register Town Elders and keep every member's information in order." : "You keep every member's information in order."}>
      {isLoading && <p className="text-sm text-[var(--text-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
      {overview && (
        <div className="lg:col-span-2 space-y-6">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <KpiTile label="Registered by you" value={overview.my_registrations_total} color="forest" icon={<IconPeople />} />
            <KpiTile label="By you, this month" value={overview.my_registrations_this_month} color="violet" icon={<IconPeople />} />
            <KpiTile label="In your register" value={overview.registry.total} color="forest" icon={<IconPeople />} />
            <KpiTile label="Missing date of birth" value={overview.registry.by_age_band.unknown} color="gold" icon={<IconPeople />} />
          </div>
          <SectionCard title="Registrar tools" eyebrow="Where to work" accent="forest">
            <div className="flex flex-wrap gap-4 text-sm">
              <FolioLink href="/members">Members — search, edit, register</FolioLink>
              <FolioLink href="/members/analytics">Full registry analytics</FolioLink>
              <FolioLink href="/inactive-members">Inactive members</FolioLink>
            </div>
          </SectionCard>
          <RegistryAnalyticsView data={overview.registry} />
        </div>
      )}
    </DashboardPageShell>
  );
}
