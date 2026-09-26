"use client";

import "@/styles/family-registry-tokens.css";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api/dashboard";
import type { ArrearsWorklistRow } from "@/lib/api/members";
import { formatCedis } from "@/lib/formatCedis";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";
import { KpiTile, SectionCard, FolioLink } from "@/components/dashboard/DashboardVisuals";
import { TrendChart } from "@/components/dashboard/TrendChart";
import { IconMoney, IconPeople, IconWarning } from "@/components/icons/DashboardIcons";

interface Perf { collected_total?: string; payment_count?: number; [k: string]: unknown }
interface ArrearsOverview {
  members_owing_count: number; total_arrears_outstanding: string; closed_funerals_with_arrears: number; largest_single_debt: string;
  worklist: ArrearsWorklistRow[]; today_performance: Perf; week_performance: Perf; collections_trend: { date: string; total: string }[];
}

/**
 * "The arrears collector should have more options, and should be able to
 * clear or collect community members' arrears before they can pay the
 * current bills." Built around closed-funeral debt — the worklist of
 * everyone owing, largest first — not today's open funeral.
 */
export default function ArrearsCollectorDashboardPage() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const ov = data?.sections?.arrears_collector_overview as ArrearsOverview | undefined;

  return (
    <DashboardPageShell folio="Folio VII" register="Arrears Register" title="Arrears Collection" subtitle="What was left owing after funerals closed — cleared oldest first, before any current bill.">
      {isLoading && <p className="text-sm text-[var(--text-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
      {ov && (
        <div className="lg:col-span-2 space-y-6">
          <form onSubmit={(e) => { e.preventDefault(); if (q.trim()) router.push(`/arrears-desk?q=${encodeURIComponent(q.trim())}`); }} className="flex gap-2">
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a member to collect from…" className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm" />
            <button type="submit" className="rounded-lg bg-[var(--primary)] px-4 py-2.5 text-sm font-semibold text-white">Open Arrears Desk</button>
          </form>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <KpiTile label="Members owing" value={ov.members_owing_count} color="clay" icon={<IconPeople />} />
            <KpiTile label="Total arrears outstanding" value={formatCedis(ov.total_arrears_outstanding)} color="clay" icon={<IconMoney />} />
            <KpiTile label="Closed funerals with arrears" value={ov.closed_funerals_with_arrears} color="gold" icon={<IconWarning />} />
            <KpiTile label="Collected by you today" value={formatCedis(String(ov.today_performance?.collected_total ?? "0"))} color="forest" icon={<IconMoney />} />
          </div>
          <div className="grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2">
              <SectionCard title="Who owes" eyebrow={`${ov.worklist.length} member(s), largest total first`} accent="clay">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wide text-[var(--text-soft)]"><th className="py-2 font-medium">Member</th><th className="py-2 font-medium">Oldest debt</th><th className="py-2 text-right font-medium">Funerals</th><th className="py-2 text-right font-medium">Owes</th></tr></thead>
                  <tbody className="divide-y divide-[var(--border-soft)]">
                    {ov.worklist.map((r) => (
                      <tr key={r.member_id}>
                        <td className="py-2.5"><Link href={`/arrears-desk?member=${r.member_id}`} className="font-medium hover:underline">{r.member_name}</Link><p className="text-xs text-[var(--text-soft)]">{r.family_name ?? "No family"}{r.phone ? ` · ${r.phone}` : ""}</p></td>
                        <td className="py-2.5 text-xs">{r.oldest_deceased_name}</td>
                        <td className="py-2.5 text-right font-mono">{r.funeral_count}</td>
                        <td className="py-2.5 text-right font-mono" style={{ color: "var(--clay-red)" }}>{formatCedis(r.total_owed)}</td>
                      </tr>
                    ))}
                    {ov.worklist.length === 0 && <tr><td colSpan={4} className="py-3 text-xs text-[var(--text-soft)]">Nobody owes on a closed funeral. Nothing to collect.</td></tr>}
                  </tbody>
                </table>
              </SectionCard>
            </div>
            <div className="space-y-6">
              <SectionCard title="This week" eyebrow="Collected by you" accent="forest">
                <p className="text-2xl font-semibold" style={{ color: "var(--forest)" }}>{formatCedis(String(ov.week_performance?.collected_total ?? "0"))}</p>
                <p className="mt-1 text-xs text-[var(--text-soft)]">{String(ov.week_performance?.payment_count ?? 0)} payment(s)</p>
                <div className="mt-3"><FolioLink href="/arrears-corrections">Arrears corrections</FolioLink></div>
              </SectionCard>
              <SectionCard title="Collections trend" eyebrow="Community-wide, last 7 days" accent="gold">
                <TrendChart data={ov.collections_trend} />
              </SectionCard>
            </div>
          </div>
        </div>
      )}
    </DashboardPageShell>
  );
}
