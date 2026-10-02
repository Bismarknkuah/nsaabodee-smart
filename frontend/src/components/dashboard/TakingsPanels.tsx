"use client";

import { useState } from "react";
import Link from "next/link";
import { formatCedis } from "@/lib/formatCedis";
import { SectionCard } from "@/components/dashboard/DashboardVisuals";

export interface TakingsTotals { today: string; week: string; all_time: string; contributions_all_time: string; gifts_all_time: string }
export interface TakingsDay { date: string; contributions: string; gifts: string; total: string; count: number }
export interface TakingsFuneral { funeral_id: string; deceased_name: string; status: string; contributions: string; gifts: string; total: string; count: number }
export interface MyTakings { totals: TakingsTotals; by_day: TakingsDay[]; by_funeral: TakingsFuneral[] }
export interface CollectorRow { collector_id: string; username: string; role: string; role_label: string; totals: TakingsTotals; by_funeral: TakingsFuneral[] }
export interface CollectorsTakings { collectors: CollectorRow[]; totals: TakingsTotals; by_day: TakingsDay[]; family_name?: string }

/** "Each collector can see what they have received daily and for each funeral." */
export function MyTakingsPanel({ takings }: { takings?: MyTakings }) {
  if (!takings) return null;
  // Defensive: a partial payload must degrade to zeros, not throw — an unhandled throw here takes down
  // the whole dashboard (the same failure class as the gift_cash incident).
  const totals = takings.totals ?? { today: "0", week: "0", all_time: "0", contributions_all_time: "0", gifts_all_time: "0" };
  const byDay = takings.by_day ?? [];
  const byFuneral = takings.by_funeral ?? [];
  const max = Math.max(1, ...byDay.map((d) => Number(d.total)));
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <SectionCard title="What you've received, daily" eyebrow={`Last 14 days · today ${formatCedis(totals.today)} · this week ${formatCedis(totals.week)}`} accent="forest">
        <ul className="flex h-32 items-end gap-1">
          {byDay.map((d) => (
            <li key={d.date} className="group relative flex flex-1 flex-col items-center justify-end" title={`${new Date(d.date).toLocaleDateString()} · ${formatCedis(d.total)} · ${d.count} record(s)`}>
              <div className="w-full rounded-t" style={{ height: `${(Number(d.total) / max) * 100}%`, minHeight: Number(d.total) > 0 ? 3 : 0, backgroundColor: "var(--forest)" }} />
              <span className="mt-1 text-[9px] text-[var(--text-soft)]">{new Date(d.date).getDate()}</span>
            </li>
          ))}
        </ul>
        <p className="mt-2 text-xs text-[var(--text-soft)]">All time: {formatCedis(totals.all_time)}{Number(totals.gifts_all_time) > 0 ? ` (contributions ${formatCedis(totals.contributions_all_time)} · gifts ${formatCedis(totals.gifts_all_time)})` : ""}</p>
      </SectionCard>
      <SectionCard title="What you've received, per funeral" eyebrow={`${byFuneral.length} funeral(s), largest first`} accent="gold">
        <FuneralRows rows={byFuneral} />
      </SectionCard>
    </div>
  );
}

/** "The financial secretary can see all money received from all community collectors" / "the family treasurer should see all money collected." */
export function CollectorsTakingsPanel({ data, title, eyebrow }: { data?: CollectorsTakings; title: string; eyebrow: string }) {
  const [open, setOpen] = useState<string | null>(null);
  if (!data) return null;
  return (
    <SectionCard title={title} eyebrow={`${eyebrow} · today ${formatCedis(data.totals.today)} · this week ${formatCedis(data.totals.week)} · all time ${formatCedis(data.totals.all_time)}`} accent="forest">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wide text-[var(--text-soft)]"><th className="py-2 font-medium">Collector</th><th className="py-2 text-right font-medium">Today</th><th className="py-2 text-right font-medium">This week</th><th className="py-2 text-right font-medium">All time</th></tr></thead>
        <tbody className="divide-y divide-[var(--border-soft)]">
          {data.collectors.map((c) => (
            <>
              <tr key={c.collector_id} className="cursor-pointer hover:bg-[var(--bg)]" onClick={() => setOpen(open === c.collector_id ? null : c.collector_id)}>
                <td className="py-2.5"><span className="font-medium">{c.username}</span><p className="text-xs text-[var(--text-soft)]">{c.role_label} · {c.by_funeral.length} funeral(s) {open === c.collector_id ? "▴" : "▾"}</p></td>
                <td className="py-2.5 text-right font-mono">{formatCedis(c.totals.today)}</td>
                <td className="py-2.5 text-right font-mono">{formatCedis(c.totals.week)}</td>
                <td className="py-2.5 text-right font-mono" style={{ color: "var(--forest)" }}>{formatCedis(c.totals.all_time)}</td>
              </tr>
              {open === c.collector_id && (
                <tr key={`${c.collector_id}-detail`}><td colSpan={4} className="bg-[var(--bg)] px-3 py-2"><FuneralRows rows={c.by_funeral} compact /></td></tr>
              )}
            </>
          ))}
          {data.collectors.length === 0 && <tr><td colSpan={4} className="py-3 text-xs text-[var(--text-soft)]">No money has been received yet.</td></tr>}
        </tbody>
      </table>
    </SectionCard>
  );
}

function FuneralRows({ rows, compact }: { rows: TakingsFuneral[]; compact?: boolean }) {
  if (rows.length === 0) return <p className="text-xs text-[var(--text-soft)]">Nothing received yet.</p>;
  return (
    <ul className={`divide-y divide-[var(--border-soft)] ${compact ? "text-xs" : "text-sm"}`}>
      {rows.map((f) => (
        <li key={f.funeral_id} className="flex items-center justify-between gap-3 py-1.5">
          <div><Link href={`/funerals/${f.funeral_id}`} className="font-medium hover:underline">{f.deceased_name}</Link><span className="ml-2 text-[var(--text-soft)]">{f.status} · {f.count} record(s){Number(f.gifts) > 0 ? ` · gifts ${formatCedis(f.gifts)}` : ""}</span></div>
          <span className="font-mono" style={{ color: "var(--forest)" }}>{formatCedis(f.total)}</span>
        </li>
      ))}
    </ul>
  );
}
