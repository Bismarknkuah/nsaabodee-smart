"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { formatCedis } from "@/lib/formatCedis";
import { paymentReversalsApi } from "@/lib/api/paymentReversals";
import { SectionCard } from "@/components/dashboard/DashboardVisuals";

export interface ChaseRow { member_id: string; member_name: string; phone?: string; family_name?: string | null; total_owed: string; funeral_count?: number; oldest_deceased_name?: string; /** What the money is for, when it is not a funeral (e.g. a welfare campaign). */ purpose?: string }
export interface RecentEntry { kind: "contribution" | "gift"; id: string; at: string; amount: string; method: string; who: string; deceased_name: string }

const METHOD_LABEL: Record<string, string> = { cash: "Cash", mobile_money: "Mobile Money", bank: "Bank", other: "Other" };

/** Call / text a member without leaving the list. Real tel: and sms: links — they work on any phone; nothing is sent from here. */
export function ContactActions({ row }: { row: ChaseRow }) {
  if (!row.phone) return <span className="text-[10px] text-[var(--text-soft)]">no phone</span>;
  const first = row.member_name.split(" ")[0];
  const toward = row.purpose ?? (row.oldest_deceased_name ? `${row.oldest_deceased_name}'s funeral` : "");
  const body = encodeURIComponent(`Hello ${first}, a gentle reminder: GH₵${Number(row.total_owed).toFixed(2)} is outstanding${toward ? ` toward ${toward}` : ""}. Thank you.`);
  return (
    <span className="flex gap-2 text-xs font-medium">
      <a href={`tel:${row.phone}`} className="text-[var(--primary)] hover:underline">Call</a>
      <a href={`sms:${row.phone}?body=${body}`} className="text-[var(--primary)] hover:underline">Text</a>
    </span>
  );
}

/** What to hand over at the end of the day: cash in hand versus what went straight to an account. */
export function HandoverCard({ byMethod, total }: { byMethod?: Record<string, string>; total?: string }) {
  if (!byMethod) return null;
  const rows = Object.entries(byMethod).filter(([, v]) => Number(v) > 0);
  return (
    <SectionCard title="Today's handover" eyebrow="By how it was paid" accent="forest">
      <ul className="space-y-2 text-sm">
        {(rows.length ? rows : [["cash", "0"]]).map(([k, v]) => (
          <li key={k} className="flex justify-between"><span className="text-[var(--text-soft)]">{METHOD_LABEL[k] ?? k}</span><span className="font-mono">{formatCedis(v)}</span></li>
        ))}
      </ul>
      <div className="mt-3 flex justify-between border-t border-[var(--border)] pt-3 text-lg font-semibold"><span>Total today</span><span style={{ color: "var(--forest)" }}>{formatCedis(total ?? "0")}</span></div>
      <p className="mt-2 text-xs text-[var(--text-soft)]">Cash is what you physically hand over; Mobile Money and Bank are already in the account.</p>
    </SectionCard>
  );
}

/** Who to chase, in two tabs: what is owed on funerals still open, and arrears from funerals that closed. */
export function WorklistTabs({ owing, arrears }: { owing?: { members_owing_count: number; total_owed: string; rows: ChaseRow[] }; arrears?: { members_owing_count: number; total_arrears_outstanding: string; worklist: ChaseRow[] } }) {
  const [tab, setTab] = useState<"owing" | "arrears">("owing");
  const active = tab === "owing" ? owing?.rows ?? [] : arrears?.worklist ?? [];
  const tabBtn = (id: "owing" | "arrears", label: string, n: number) => (
    <button onClick={() => setTab(id)} className={`rounded-lg px-3 py-1.5 text-sm font-medium ${tab === id ? "bg-[var(--primary)] text-white" : "border border-[var(--border)] hover:border-[var(--primary)]"}`}>{label} <span className="opacity-80">({n})</span></button>
  );
  return (
    <SectionCard title="Who to chase" eyebrow="Only people inside your own jurisdiction" accent="clay">
      <div className="flex flex-wrap gap-2">
        {tabBtn("owing", "Owing now", owing?.members_owing_count ?? 0)}
        {arrears && tabBtn("arrears", "Arrears", arrears.members_owing_count)}
      </div>
      <p className="mt-2 text-xs text-[var(--text-soft)]">{tab === "owing" ? `${formatCedis(owing?.total_owed ?? "0")} owed on open funerals.` : `${formatCedis(arrears?.total_arrears_outstanding ?? "0")} left owing on closed funerals — collected oldest first.`}</p>
      <ul className="mt-2 divide-y divide-[var(--border-soft)]">
        {active.slice(0, 15).map((r) => (
          <li key={r.member_id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{r.member_name}</p>
              <p className="text-xs text-[var(--text-soft)]">{r.family_name ?? "No family"}{r.oldest_deceased_name ? ` · ${r.oldest_deceased_name}` : ""}{r.phone ? ` · ${r.phone}` : ""}</p>
            </div>
            <div className="flex items-center gap-3">
              <ContactActions row={r} />
              <Link href={tab === "arrears" ? `/arrears-desk?member=${r.member_id}` : `/front-desk?q=${encodeURIComponent(r.member_name)}`} className="rounded-lg bg-[var(--forest)] px-3 py-1 text-xs font-semibold text-white">Collect</Link>
              <span className="w-24 text-right font-mono text-sm" style={{ color: "var(--clay-red)" }}>{formatCedis(r.total_owed)}</span>
            </div>
          </li>
        ))}
        {active.length === 0 && <li className="py-3 text-xs text-[var(--text-soft)]">{tab === "owing" ? "Nobody in your jurisdiction owes on an open funeral." : "Nobody in your jurisdiction owes on a closed funeral."}</li>}
      </ul>
    </SectionCard>
  );
}

/** The latest entries, each correctable: a wrong amount is flagged the moment it is spotted, and still needs a second officer to approve. */
export function RecentEntries({ rows }: { rows?: RecentEntry[] }) {
  const qc = useQueryClient();
  const [done, setDone] = useState<string | null>(null);
  const request = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => paymentReversalsApi.request(id, reason),
    onSuccess: (_d, v) => { setDone(v.id); qc.invalidateQueries({ queryKey: ["payment-reversals"] }); },
  });
  if (!rows) return null;
  return (
    <SectionCard title="Your latest entries" eyebrow="Spotted a mistake? Flag it here — a second officer approves any correction" accent="gold">
      <ul className="divide-y divide-[var(--border-soft)]">
        {rows.map((r) => (
          <li key={`${r.kind}-${r.id}`} className="flex items-center justify-between gap-3 py-2 text-sm">
            <div className="min-w-0"><p className="truncate">{r.who} <span className="text-xs text-[var(--text-soft)]">· {r.kind === "gift" ? "gift" : "contribution"} · {r.deceased_name}</span></p><p className="text-xs text-[var(--text-soft)]">{new Date(r.at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })} · {METHOD_LABEL[r.method] ?? r.method}</p></div>
            <div className="flex items-center gap-3">
              <span className="font-mono">{formatCedis(r.amount)}</span>
              {r.kind === "contribution" && (done === r.id ? <span className="text-xs" style={{ color: "var(--forest)" }}>Flagged ✓</span> : (
                <button onClick={() => { const reason = window.prompt("What is wrong with this entry? (this goes on the permanent record)"); if (reason && reason.trim()) request.mutate({ id: r.id, reason: reason.trim() }); }} className="text-xs font-medium text-[var(--clay-red)] hover:underline">Flag error</button>
              ))}
            </div>
          </li>
        ))}
        {rows.length === 0 && <li className="py-2 text-xs text-[var(--text-soft)]">Nothing recorded yet.</li>}
      </ul>
      {request.isError && <p className="mt-2 text-xs text-[var(--clay-red)]">{request.error.message}</p>}
    </SectionCard>
  );
}

/** The four places a collector actually goes, as tiles. */
export function CollectorActions({ links }: { links: { href: string; label: string; hint: string }[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {links.map((l) => (
        <Link key={l.href} href={l.href} className="rounded-[var(--radius)] bg-[var(--card)] px-4 py-3 transition-colors hover:border-[var(--primary)]" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
          <p className="font-medium">{l.label}</p><p className="mt-0.5 text-xs text-[var(--text-soft)]">{l.hint}</p>
        </Link>
      ))}
    </div>
  );
}
