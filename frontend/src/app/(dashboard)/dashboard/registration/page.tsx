"use client";

import "@/styles/family-registry-tokens.css";
import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api/dashboard";
import type { MemberRegistryAnalytics } from "@/lib/api/members";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";
import { RoleHome, MonthlyMethodChart, HomeTable } from "@/components/dashboard/RoleHome";

import { KpiTile, SectionCard } from "@/components/dashboard/DashboardVisuals";
import { RegistryAnalyticsView } from "@/components/members/RegistryAnalyticsView";
import { RegisterMemberDialog } from "@/components/members/RegisterMemberDialog";
import { IconPeople } from "@/components/icons/DashboardIcons";

interface Gap { count: number; rows: { id: string; full_name: string; family_name: string | null }[] }
interface RegistrationOverview {
  registry: MemberRegistryAnalytics;
  my_registrations_total: number;
  my_registrations_this_month: number;
  my_registrations_last_7_days: number;
  level: "community" | "family";
  data_quality: { missing_phone: Gap; missing_date_of_birth: Gap; missing_ghana_card: Gap; without_login: Gap; without_family: Gap };
  ledger_activity: { at: string; member_id: string; member_name: string; to_ledger: "family" | "town_elders"; by: string | null; description: string }[];
  // The community registrar keeps the Town Elders register too — "the community admin and the town registration officer register them."
  town_elders_register?: { count: number; elders: { id: string; full_name: string; title: string; family_name: string | null; status: string }[] };
  families_without_registration_officer?: { id: string; name: string }[];
}

const GAPS: [keyof RegistrationOverview["data_quality"], string, string][] = [
  ["missing_phone", "No phone number", "Can't be reached for reminders or receipts"],
  ["missing_date_of_birth", "No date of birth", "Left out of the age breakdown"],
  ["missing_ghana_card", "No Ghana Card", "Harder to tell apart from a duplicate"],
  ["without_login", "No login yet", "Can't see their own receipts or dues"],
  ["without_family", "No family", "Every member must belong to a family"],
];

/**
 * The registrar's workspace. Register right here; see what still needs fixing in the
 * register; watch members move between ledgers; and (for the community registrar)
 * keep the Town Elders register. Member information only — no collections, expenses
 * or balances anywhere on this page.
 */
export default function RegistrationDashboardPage() {
  const [registering, setRegistering] = useState(false);
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const ov = data?.sections?.registration_overview as RegistrationOverview | undefined;
  const scope = ov?.registry.scope;
  const scopeLabel = scope === "family" ? "Your family's register" : scope === "town_elders" ? "Town Elders register" : "Community register";
  const gapTotal = ov ? GAPS.reduce((n, [k]) => n + ov.data_quality[k].count, 0) : 0;
  const card = "rounded-[var(--radius)] bg-[var(--card)] px-4 py-3 transition-colors hover:border-[var(--primary)]";
  const cardStyle = { boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" } as const;

  return (
    <DashboardPageShell folio="Folio VI" register={scopeLabel} title="Registration" subtitle={ov?.level === "community" ? "You register everyone in the town — Town Elders included — and keep every member's record complete." : "You register your family's members and keep their records complete."}>
      {isLoading && <p className="text-sm text-[var(--text-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
      {ov && (
        <div className="lg:col-span-2 space-y-6">
          {ov.level === "community" && (
            <RoleHome
              title="Town Registration" subtitle="Handle town members, registrations and related records."
              tiles={[
                { label: "Total town members", value: String(ov.registry.total), sub: "Registered", color: "var(--primary)" },
                { label: "New registrations", value: String(ov.my_registrations_this_month), sub: "By you, this month", color: "var(--forest)" },
                { label: "Records to complete", value: String(Object.values(ov.data_quality ?? {}).reduce((n, g) => n + (g as { count: number }).count, 0)), sub: "Missing details", color: "var(--clay-red)" },
                { label: "Town elders", value: String(ov.town_elders_register?.count ?? 0), sub: "On the elders' register", color: "var(--gold)" },
              ]}
              main={<HomeTable title="Recent registrations" href="/members" columns={["Date", "Name", "Family"]} rows={(ov.registry.recent_registrations ?? []).slice(0, 8).map((r) => [new Date(r.created_at).toLocaleDateString(), r.full_name, r.family_name ?? "—"])} empty="No registration yet." />}
              actions={[{ href: "/members", label: "Register member" }, { href: "/town-elders-ledger", label: "View town elders" }, { href: "/members/analytics", label: "Generate reports" }, { href: "/documents", label: "Documents" }, { href: "/profile", label: "Settings" }]}
            />
          )}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <button onClick={() => setRegistering(true)} className="rounded-[var(--radius)] bg-[var(--primary)] px-4 py-3 text-left text-white transition-opacity hover:opacity-90" style={{ boxShadow: "var(--shadow-sm)" }}>
              <p className="font-semibold">+ Register a member</p><p className="mt-0.5 text-xs opacity-90">Family and ledger, then details</p>
            </button>
            <Link href="/members" className={card} style={cardStyle}><p className="font-medium">Members</p><p className="mt-0.5 text-xs text-[var(--text-soft)]">Search, edit, move family or ledger, bulk upload, export</p></Link>
            <Link href="/inactive-members" className={card} style={cardStyle}><p className="font-medium">Inactive members</p><p className="mt-0.5 text-xs text-[var(--text-soft)]">Reactivate someone removed by mistake</p></Link>
            <Link href="/members/analytics" className={card} style={cardStyle}><p className="font-medium">Full analytics</p><p className="mt-0.5 text-xs text-[var(--text-soft)]">Age, gender, family, growth</p></Link>
          </div>

          <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
            <KpiTile label="By you, last 7 days" value={ov.my_registrations_last_7_days} color="forest" icon={<IconPeople />} />
            <KpiTile label="By you, this month" value={ov.my_registrations_this_month} color="violet" icon={<IconPeople />} />
            <KpiTile label="In your register" value={ov.registry.total} color="forest" icon={<IconPeople />} />
            <KpiTile label="On the Town Elders ledger" value={ov.registry.by_contribution_ledger.town_elders} color="violet" icon={<IconPeople />} />
            <KpiTile label="Records to complete" value={gapTotal} color={gapTotal > 0 ? "gold" : "forest"} icon={<IconPeople />} />
          </div>

          <SectionCard title="Records to complete" eyebrow={gapTotal === 0 ? "Nothing missing — the register is complete" : "Active members with details missing — open one to fix it"} accent="gold">
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {GAPS.map(([key, label, why]) => {
                const gap = ov.data_quality[key];
                return (
                  <div key={key} className="rounded-lg border border-[var(--border-soft)] p-3">
                    <div className="flex items-baseline justify-between"><p className="text-sm font-semibold">{label}</p><span className="font-mono text-sm" style={{ color: gap.count ? "var(--gold)" : "var(--forest)" }}>{gap.count}</span></div>
                    <p className="text-xs text-[var(--text-soft)]">{why}</p>
                    <ul className="mt-2 space-y-1 text-sm">
                      {gap.rows.slice(0, 5).map((m) => <li key={m.id}><Link href={`/members/${m.id}`} className="hover:underline">{m.full_name}</Link>{m.family_name ? <span className="text-xs text-[var(--text-soft)]"> · {m.family_name}</span> : null}</li>)}
                      {gap.count > 5 && <li className="text-xs text-[var(--text-soft)]">and {gap.count - 5} more</li>}
                      {gap.count === 0 && <li className="text-xs" style={{ color: "var(--forest)" }}>All complete ✓</li>}
                    </ul>
                  </div>
                );
              })}
            </div>
          </SectionCard>

          <div className="grid gap-6 lg:grid-cols-2">
            <SectionCard title="Ledger activity" eyebrow="Members moved between the family and Town Elders ledgers" accent="violet">
              <ul className="divide-y divide-[var(--border-soft)]">
                {ov.ledger_activity.map((a, i) => (
                  <li key={i} className="py-2 text-sm"><div className="flex justify-between gap-2"><Link href={`/members/${a.member_id}`} className="font-medium hover:underline">{a.member_name}</Link><span className="text-xs" style={{ color: a.to_ledger === "town_elders" ? "var(--violet)" : "var(--text-soft)" }}>→ {a.to_ledger === "town_elders" ? "Town Elders ledger" : "Family ledger"}</span></div><p className="text-xs text-[var(--text-soft)]">{new Date(a.at).toLocaleDateString(undefined, { dateStyle: "medium" })}{a.by ? ` · by ${a.by}` : ""}</p></li>
                ))}
                {ov.ledger_activity.length === 0 && <li className="py-2 text-xs text-[var(--text-soft)]">No one has moved ledger yet. Open a member to transfer them.</li>}
              </ul>
            </SectionCard>

            {ov.town_elders_register && (
              <SectionCard title="Town Elders register" eyebrow={`${ov.town_elders_register.count} elder(s) — every one still belongs to a family`} accent="violet">
                <ul className="divide-y divide-[var(--border-soft)]">
                  {ov.town_elders_register.elders.map((e) => (
                    <li key={e.id} className="flex items-center justify-between py-2 text-sm"><div><Link href={`/members/${e.id}`} className="font-medium hover:underline">{e.full_name}</Link><span className="ml-2 text-xs text-[var(--text-soft)]">{e.title || "elder"}{e.family_name ? ` · ${e.family_name}` : ""}</span></div><span className="text-xs text-[var(--text-soft)]">{e.status}</span></li>
                  ))}
                  {ov.town_elders_register.count === 0 && <li className="py-2 text-xs text-[var(--text-soft)]">No Town Elders yet — choose the Town Elders ledger when registering, or transfer an existing member.</li>}
                </ul>
                {ov.families_without_registration_officer && ov.families_without_registration_officer.length > 0 && (
                  <p className="mt-3 text-xs text-[var(--text-soft)]">Families with no registration officer yet: {ov.families_without_registration_officer.map((f) => f.name).join(", ")} — their Family Head or Secretary can appoint one.</p>
                )}
              </SectionCard>
            )}
          </div>

          <RegistryAnalyticsView data={ov.registry} />
        </div>
      )}
      {registering && <RegisterMemberDialog onClose={() => setRegistering(false)} />}
    </DashboardPageShell>
  );
}
