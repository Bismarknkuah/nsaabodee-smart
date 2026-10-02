"use client";

import Link from "next/link";
import type { ReactNode } from "react";

/**
 * The reference design's role home: a greeting, four figures, one main panel beside a smaller one, and a rail of
 * quick actions. Each role's page mounts it first with its own real data, then its deeper panels follow.
 */
export interface HomeTile { label: string; value: string; sub: string; color: string }
export interface HomeAction { href: string; label: string }

export function RoleHome({ title, subtitle, tiles, main, side, actions, actionsTitle = "Quick actions" }: {
  title: string; subtitle: string; tiles: HomeTile[]; main: ReactNode; side?: ReactNode; actions: HomeAction[]; actionsTitle?: string;
}) {
  const now = new Date();
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_260px]">
      <div className="space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div><p className="text-2xl font-semibold">{title}</p><p className="text-sm text-[var(--text-soft)]">{subtitle}</p></div>
          <p className="text-xs text-[var(--text-soft)]">{now.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" })} · {now.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</p>
        </div>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {tiles.map((t) => (
            <div key={t.label} className="flex items-center gap-3 rounded-[var(--radius)] bg-[var(--card)] p-4" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
              <span aria-hidden className="h-10 w-10 shrink-0 rounded-xl" style={{ backgroundColor: t.color, opacity: 0.9 }} />
              <div className="min-w-0"><p className="text-xs text-[var(--text-soft)]">{t.label}</p><p className="truncate text-xl font-semibold" style={{ color: t.color }}>{t.value}</p><p className="text-[11px] text-[var(--text-soft)]">{t.sub}</p></div>
            </div>
          ))}
        </div>
        <div className={`grid gap-6 ${side ? "lg:grid-cols-2" : ""}`}>
          <div className="rounded-[var(--radius)] bg-[var(--card)] p-5" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>{main}</div>
          {side && <div className="rounded-[var(--radius)] bg-[var(--card)] p-5" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>{side}</div>}
        </div>
      </div>
      <aside>
        <div className="rounded-[var(--radius)] bg-[var(--card)] p-4" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
          <p className="text-sm font-semibold">{actionsTitle}</p>
          <div className="mt-2 space-y-2 text-sm">
            {actions.map((a) => <Link key={a.label} href={a.href} className="block rounded-lg bg-[var(--bg)] px-3 py-2 font-medium hover:bg-[var(--gold-soft)]">{a.label}</Link>)}
          </div>
        </div>
      </aside>
    </div>
  );
}

/** A small stacked bar chart, month by month, by payment method — the "trends" / "collections overview" panel. */
export function MonthlyMethodChart({ months, year, title }: { months: { month: string; cash: string; mobile_money: string; bank: string; other: string }[]; year: number; title: string }) {
  const max = Math.max(1, ...months.map((m) => Number(m.cash) + Number(m.mobile_money) + Number(m.bank) + Number(m.other)));
  const parts = [["cash", "var(--primary)"], ["mobile_money", "var(--forest)"], ["bank", "var(--violet, #6d4bd1)"], ["other", "var(--gold)"]] as const;
  return (
    <>
      <div className="flex items-center justify-between"><p className="font-semibold">{title}</p><span className="text-xs text-[var(--text-soft)]">{year}</span></div>
      <ul className="mt-3 flex h-40 items-end gap-1">
        {months.map((m) => (
          <li key={m.month} className="flex flex-1 flex-col items-center justify-end gap-0.5" title={`${m.month}: cash ${m.cash}, MoMo ${m.mobile_money}, bank ${m.bank}`}>
            <div className="flex w-full items-end gap-px">{parts.map(([k, c]) => <div key={k} className="flex-1 rounded-t" style={{ height: `${(Number(m[k]) / max) * 140}px`, backgroundColor: c, minHeight: Number(m[k]) > 0 ? 2 : 0 }} />)}</div>
            <span className="text-[9px] text-[var(--text-soft)]">{new Date(m.month + "-01").toLocaleDateString(undefined, { month: "short" })}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 flex gap-3 text-[10px] text-[var(--text-soft)]"><span>■ Cash</span><span style={{ color: "var(--forest)" }}>■ MoMo</span><span>■ Bank</span><span style={{ color: "var(--gold)" }}>■ Other</span></p>
    </>
  );
}

/** A compact table for the "recent …" panels. */
export function HomeTable({ title, href, columns, rows, empty }: { title: string; href?: string; columns: string[]; rows: ReactNode[][]; empty: string }) {
  return (
    <>
      <div className="flex items-center justify-between"><p className="font-semibold">{title}</p>{href && <Link href={href} className="text-xs text-[var(--primary)] hover:underline">View all</Link>}</div>
      <table className="mt-2 w-full text-xs">
        <thead><tr className="border-b border-[var(--border)] text-left uppercase tracking-wide text-[var(--text-soft)]">{columns.map((c) => <th key={c} className="py-1.5 font-medium">{c}</th>)}</tr></thead>
        <tbody className="divide-y divide-[var(--border-soft)]">
          {rows.map((r, i) => <tr key={i}>{r.map((cell, j) => <td key={j} className="py-1.5 pr-2">{cell}</td>)}</tr>)}
          {rows.length === 0 && <tr><td colSpan={columns.length} className="py-3 text-[var(--text-soft)]">{empty}</td></tr>}
        </tbody>
      </table>
    </>
  );
}
