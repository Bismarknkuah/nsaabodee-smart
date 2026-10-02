"use client";

import "@/styles/family-registry-tokens.css";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api/dashboard";
import { formatCedis } from "@/lib/formatCedis";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";
import { KpiTile, SectionCard } from "@/components/dashboard/DashboardVisuals";
import { JurisdictionBanner, type Jurisdiction } from "@/components/dashboard/JurisdictionBanner";
import { HandoverCard, RecentEntries, type RecentEntry } from "@/components/dashboard/CollectorParts";
import { MyTakingsPanel, type MyTakings } from "@/components/dashboard/TakingsPanels";

import { IconMoney, IconFuneral } from "@/components/icons/DashboardIcons";

interface Tot { count: number; cash_total: string }
interface GiftOverview {
  jurisdiction: Jurisdiction;
  my_takings?: (MyTakings & { today_by_method?: Record<string, string>; recent?: RecentEntry[] }); today: Tot; week: Tot; all_time: Tot;
  open_funerals: { funeral_id: string; deceased_name: string; family_name: string; gift_count: number; gift_cash_total: string }[];
}

/**
 * "For visitors level, there should be a collector for collecting guest
 * contribution." The gifts desk: what this collector has taken from
 * guests, and every open funeral where guests may still be giving.
 */
export default function GiftCollectorDashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const ov = data?.sections?.gift_collector_overview as GiftOverview | undefined;
  return (
    <DashboardPageShell folio="Folio VIII" register="Guest Register" title="Guest Contributions" subtitle="Donations and gifts from guests and sympathisers — recorded at the funeral's gifts desk, receipted, and credited to the right receiver.">
      {isLoading && <p className="text-sm text-[var(--text-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
      {ov && (
        <div className="lg:col-span-2 space-y-6">
          <JurisdictionBanner jurisdiction={ov.jurisdiction} />
          <div className="grid gap-6 lg:grid-cols-2">
            <HandoverCard byMethod={ov.my_takings?.today_by_method} total={ov.my_takings?.totals.today} />
            <RecentEntries rows={ov.my_takings?.recent} />
          </div>
          <MyTakingsPanel takings={ov.my_takings} />
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <KpiTile label="Gifts today (by you)" value={ov.today.count} color="forest" icon={<IconMoney />} />
            <KpiTile label="Cash today (by you)" value={formatCedis(ov.today.cash_total)} color="forest" icon={<IconMoney />} />
            <KpiTile label="This week (by you)" value={formatCedis(ov.week.cash_total)} color="gold" icon={<IconMoney />} />
            <KpiTile label="Open funerals" value={ov.open_funerals.length} color="violet" icon={<IconFuneral />} />
          </div>
          <SectionCard title="Where guests are giving" eyebrow="Open funerals — open one to record a gift at its desk" accent="violet">
            <ul className="divide-y divide-[var(--border-soft)]">
              {ov.open_funerals.map((f) => (
                <li key={f.funeral_id} className="flex items-center justify-between gap-3 py-2.5">
                  <div><Link href={`/funerals/${f.funeral_id}`} className="text-sm font-medium hover:underline">{f.deceased_name}</Link><p className="text-xs text-[var(--text-soft)]">{f.family_name} · {f.gift_count} gift{f.gift_count === 1 ? "" : "s"} so far</p></div>
                  <span className="font-mono text-sm" style={{ color: "var(--forest)" }}>{formatCedis(f.gift_cash_total)}</span>
                </li>
              ))}
              {ov.open_funerals.length === 0 && <li className="py-2 text-xs text-[var(--text-soft)]">No funeral is open right now.</li>}
            </ul>
          </SectionCard>
        </div>
      )}
    </DashboardPageShell>
  );
}
