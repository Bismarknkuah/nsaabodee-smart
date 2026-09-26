"use client";

import Link from "next/link";
import type { MemberRegistryAnalytics } from "@/lib/api/members";
import { KpiTile, SectionCard } from "@/components/dashboard/DashboardVisuals";
import { IconPeople } from "@/components/icons/DashboardIcons";

/** The registry's analytics visuals, shared by the Member Registry page and the registration officers' own dashboard. */
export function RegistryAnalyticsView({ data }: { data: MemberRegistryAnalytics }) {
  return (
    <>

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-6">
          <KpiTile label="Registered" value={data.total} color="forest" icon={<IconPeople />} />
          <KpiTile label="Active" value={data.by_status.active ?? 0} color="forest" icon={<IconPeople />} />
          <KpiTile label="Inactive" value={data.by_status.inactive ?? 0} color="gold" icon={<IconPeople />} />
          <KpiTile label="Deceased" value={data.by_status.deceased ?? 0} color="clay" icon={<IconPeople />} />
          <KpiTile label="Town Elders" value={data.town_elders} color="violet" icon={<IconPeople />} />
          <KpiTile label="With a login" value={data.with_login} color="violet" icon={<IconPeople />} />
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <SectionCard title="By gender" eyebrow="Registered members" accent="forest">
        <Bars rows={Object.entries(data.by_gender).map(([k, v]) => [cap(k), v])} color="var(--forest)" />
          </SectionCard>
          <SectionCard title="By age" eyebrow="From date of birth where recorded" accent="violet">
        <Bars rows={[["Under 18", data.by_age_band.under_18], ["18–35", data.by_age_band["18_35"]], ["36–50", data.by_age_band["36_50"]], ["51–65", data.by_age_band["51_65"]], ["Over 65", data.by_age_band.over_65], ["Not recorded", data.by_age_band.unknown]]} color="var(--violet)" />
          </SectionCard>
          <SectionCard title="Defaulter tiers" eyebrow="Standing on closed funerals" accent="gold">
        <Bars rows={Object.entries(data.by_defaulter_tier).map(([k, v]) => [k === "none" ? "In good standing" : cap(k), v])} color="var(--gold)" />
          </SectionCard>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <SectionCard title="Family by family" eyebrow={`${data.by_family.length} famil${data.by_family.length === 1 ? "y" : "ies"}`} accent="forest">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wide text-[var(--text-soft)]"><th className="py-2 font-medium">Family</th><th className="py-2 text-right font-medium">Members</th><th className="py-2 text-right font-medium">Active</th><th className="py-2 text-right font-medium">Deceased</th></tr></thead>
          <tbody className="divide-y divide-[var(--border-soft)]">
            {data.by_family.map((f) => (
              <tr key={f.family_id ?? "none"}>
                <td className="py-2">{f.family_name}</td>
                <td className="py-2 text-right font-mono">{f.total}</td>
                <td className="py-2 text-right font-mono" style={{ color: "var(--forest)" }}>{f.active}</td>
                <td className="py-2 text-right font-mono text-[var(--text-soft)]">{f.deceased}</td>
              </tr>
            ))}
          </tbody>
        </table>
          </SectionCard>
          <SectionCard title="Registrations, last 12 months" eyebrow="New members per month" accent="violet">
        <Bars rows={data.registrations_by_month.map((m) => [m.month, m.count])} color="var(--primary)" />
        {data.registrations_by_month.length === 0 && <p className="text-xs text-[var(--text-soft)]">No registrations in the last year.</p>}
          </SectionCard>
          <SectionCard title="Recently registered" eyebrow="Newest first" accent="gold">
        <ul className="divide-y divide-[var(--border-soft)]">
          {data.recent_registrations.map((m) => (
            <li key={m.id} className="flex items-center justify-between py-2">
              <div>
                <Link href={`/members/${m.id}`} className="text-sm font-medium hover:underline">{m.full_name}</Link>
                <p className="text-xs text-[var(--text-soft)]">{m.family_name ?? "No family"}</p>
              </div>
              <span className="text-xs text-[var(--text-soft)]">{new Date(m.created_at).toLocaleDateString(undefined, { dateStyle: "medium" })}</span>
            </li>
          ))}
        </ul>
          </SectionCard>
        </div>
    </>
  );
}

function cap(s: string) { return s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, " "); }

export function Bars({ rows, color }: { rows: [string, number][]; color: string }) {
  const max = Math.max(1, ...rows.map(([, n]) => n));
  return (
    <ul className="space-y-2.5">
      {rows.map(([label, n]) => (
        <li key={label}>
          <div className="flex justify-between text-sm"><span>{label}</span><span className="font-mono text-xs text-[var(--text-soft)]">{n}</span></div>
          <div className="mt-1 h-2 overflow-hidden rounded-full bg-[var(--bg)]"><div className="h-full rounded-full" style={{ width: `${(n / max) * 100}%`, backgroundColor: color }} /></div>
        </li>
      ))}
    </ul>
  );
}
