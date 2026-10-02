"use client";

import "@/styles/family-registry-tokens.css";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { membersApi, arrearsApi, type ArrearsPosition } from "@/lib/api/members";
import { formatCedis } from "@/lib/formatCedis";

/**
 * The Arrears Desk — "the arrears collector should be able to clear or
 * collect community members' arrears before they can pay the current
 * bills." Look a member up, see every arrear oldest first with the
 * running total, take one lump sum that the platform splits oldest-first,
 * and watch the current bill unlock the moment the arrears are cleared.
 */
export default function ArrearsDeskPage() {
  const params = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [memberId, setMemberId] = useState<string | null>(params.get("member"));
  const { data: results } = useQuery({ queryKey: ["arrears-desk-search", q], queryFn: () => membersApi.list({ search: q }), enabled: q.trim().length >= 2 && !memberId });
  useEffect(() => { const m = params.get("member"); if (m) setMemberId(m); }, [params]);

  return (
    <div className="font-body min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="border-b border-[var(--border)] bg-[var(--card)] px-8 py-6">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-soft)]">Arrears Register</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Arrears Desk</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--text-soft)]">Arrears are cleared oldest first. A current bill only opens once every arrear before it is settled.</p>
      </header>
      <main className="px-8 py-8">
        {!memberId && (
          <div className="max-w-xl">
            <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Member name, phone, or membership number…" className="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-3 text-base" />
            <ul className="mt-3 divide-y divide-[var(--border-soft)] rounded-[var(--radius)] bg-[var(--card)]" style={{ boxShadow: "var(--shadow-sm)" }}>
              {(results ?? []).map((m) => (
                <li key={m.id}><button onClick={() => setMemberId(m.id)} className="flex w-full items-center justify-between px-4 py-3 text-left text-sm hover:bg-[var(--bg)]"><span><span className="font-medium">{m.full_name}</span><span className="ml-2 text-xs text-[var(--text-soft)]">{typeof m.family === "string" ? m.family : (m.family as { name?: string } | null)?.name ?? ""}</span></span><span className="text-xs text-[var(--text-soft)]">{m.membership_number}</span></button></li>
              ))}
            </ul>
          </div>
        )}
        {memberId && <MemberArrearsPanel memberId={memberId} onBack={() => { setMemberId(null); setQ(""); }} />}
      </main>
    </div>
  );
}

function MemberArrearsPanel({ memberId, onBack }: { memberId: string; onBack: () => void }) {
  const qc = useQueryClient();
  const { data: pos, isLoading, error } = useQuery({ queryKey: ["arrears-position", memberId], queryFn: () => arrearsApi.position(memberId) });
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("cash");
  const [collectorName, setCollectorName] = useState("");
  const [opId] = useState(() => `arrears-${memberId}-${Date.now()}`);
  const [last, setLast] = useState<{ payments: { deceased_name: string; amount: string }[]; arrears_cleared: boolean } | null>(null);
  const collect = useMutation({
    mutationFn: () => arrearsApi.collect(memberId, amount, method, collectorName, `${opId}-${amount}`),
    onSuccess: (r) => { setLast(r); setAmount(""); qc.invalidateQueries({ queryKey: ["arrears-position", memberId] }); qc.invalidateQueries({ queryKey: ["dashboard"] }); },
  });
  const preview = useMemo(() => split(pos, amount), [pos, amount]);
  const card = "rounded-[var(--radius)] bg-[var(--card)] p-5";
  const cardStyle = { boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" } as const;

  if (isLoading) return <p className="text-sm text-[var(--text-soft)]">Loading…</p>;
  if (error || !pos) return <p className="text-sm text-[var(--clay-red)]">{(error as Error)?.message ?? "Could not load."}</p>;
  const owesArrears = Number(pos.total_arrears) > 0;

  return (
    <div className="max-w-4xl space-y-6">
      <button onClick={onBack} className="text-sm text-[var(--text-soft)] hover:underline">← Search again</button>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div><h2 className="text-2xl font-semibold">{pos.member_name}</h2><p className="text-sm text-[var(--text-soft)]">{pos.family_name ?? "No family"}</p></div>
        <div className="text-right"><p className="text-xs text-[var(--text-soft)]">Owes in total</p><p className="text-3xl font-semibold" style={{ color: Number(pos.total_owed) > 0 ? "var(--clay-red)" : "var(--forest)" }}>{formatCedis(pos.total_owed)}</p></div>
      </div>

      <section className={card} style={{ ...cardStyle, borderColor: owesArrears ? "color-mix(in srgb, var(--clay-red) 35%, transparent)" : "var(--border-soft)" }}>
        <div className="flex items-center justify-between"><h3 className="text-lg font-semibold" style={{ color: "var(--clay-red)" }}>Arrears — oldest first</h3><span className="font-mono text-lg" style={{ color: "var(--clay-red)" }}>{formatCedis(pos.total_arrears)}</span></div>
        {pos.arrears.length === 0 ? <p className="mt-2 text-sm" style={{ color: "var(--forest)" }}>No arrears. Everything from past funerals is settled.</p> : (
          <ol className="mt-3 divide-y divide-[var(--border-soft)]">
            {pos.arrears.map((a, i) => (
              <li key={a.obligation_id} className="flex items-center justify-between py-2.5 text-sm">
                <div><span className="mr-2 font-mono text-xs text-[var(--text-soft)]">{i + 1}.</span><span className="font-medium">{a.deceased_name}</span><span className="ml-2 text-xs text-[var(--text-soft)]">{a.collection_start_date ? new Date(a.collection_start_date).toLocaleDateString() : ""} · paid {formatCedis(a.amount_paid)} of {formatCedis(a.expected_amount)}</span></div>
                <span className="font-mono" style={{ color: "var(--clay-red)" }}>{formatCedis(a.balance)}</span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className={card} style={cardStyle}>
        <div className="flex items-center justify-between"><h3 className="text-lg font-semibold">Current bills</h3><span className="font-mono text-lg">{formatCedis(pos.total_current_bills)}</span></div>
        {!pos.current_bills_payable && pos.current_bills.length > 0 && (
          <p className="mt-2 rounded-lg px-3 py-2 text-sm" style={{ backgroundColor: "var(--gold-soft)", color: "var(--gold)" }}>🔒 Locked until the {formatCedis(pos.total_arrears)} in arrears above is cleared. Anything collected beyond the arrears flows on to these automatically.</p>
        )}
        {pos.current_bills_payable && pos.current_bills.length > 0 && <p className="mt-2 text-sm" style={{ color: "var(--forest)" }}>✓ Arrears clear — current bills are open to pay.</p>}
        <ul className="mt-3 divide-y divide-[var(--border-soft)]">
          {pos.current_bills.map((b) => <li key={b.obligation_id} className="flex items-center justify-between py-2 text-sm"><span>{b.deceased_name} <span className="text-xs text-[var(--text-soft)]">(open)</span></span><span className="font-mono">{formatCedis(b.balance)}</span></li>)}
          {pos.current_bills.length === 0 && <li className="py-2 text-xs text-[var(--text-soft)]">No open funeral bills.</li>}
        </ul>
      </section>

      {Number(pos.total_owed) > 0 && (
        <section className={card} style={cardStyle}>
          <h3 className="text-lg font-semibold">Collect</h3>
          <p className="mt-1 text-xs text-[var(--text-soft)]">Enter what {pos.member_name.split(" ")[0]} is paying now. It is applied oldest-first, and never to a newer debt while an older one stands.</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <input type="number" min="0.01" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder={`Up to ${pos.total_owed}`} className="rounded-lg border border-[var(--border)] px-3 py-2.5 text-lg font-semibold" />
            <select value={method} onChange={(e) => setMethod(e.target.value)} className="rounded-lg border border-[var(--border)] px-3 py-2.5 text-sm"><option value="cash">Cash</option><option value="mobile_money">Mobile Money</option><option value="bank">Bank</option></select>
            <input value={collectorName} onChange={(e) => setCollectorName(e.target.value)} placeholder="Your name (on the receipt)" className="rounded-lg border border-[var(--border)] px-3 py-2.5 text-sm" />
          </div>
          {preview.length > 0 && (
            <div className="mt-3 rounded-lg bg-[var(--bg)] p-3 text-sm">
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-soft)]">How this will be applied</p>
              <ul className="mt-1 space-y-0.5">{preview.map((p) => <li key={p.name} className="flex justify-between"><span>{p.name}{p.current ? " (current bill)" : ""}</span><span className="font-mono">{formatCedis(String(p.amount))}</span></li>)}</ul>
            </div>
          )}
          <div className="mt-3 flex items-center gap-3">
            <button onClick={() => collect.mutate()} disabled={collect.isPending || !amount || Number(amount) <= 0 || Number(amount) > Number(pos.total_owed)} className="rounded-lg px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50" style={{ backgroundColor: "var(--forest)" }}>{collect.isPending ? "Recording…" : "Collect"}</button>
            {Number(amount) > Number(pos.total_owed) && <span className="text-xs text-[var(--clay-red)]">More than everything owed.</span>}
            {collect.isError && <span className="text-xs text-[var(--clay-red)]">{collect.error.message}</span>}
          </div>
        </section>
      )}

      {last && (
        <section className={card} style={{ ...cardStyle, borderColor: "color-mix(in srgb, var(--forest) 35%, transparent)" }}>
          <h3 className="text-lg font-semibold" style={{ color: "var(--forest)" }}>✓ Recorded</h3>
          <ul className="mt-2 text-sm">{last.payments.map((p, i) => <li key={i} className="flex justify-between py-0.5"><span>{p.deceased_name}</span><span className="font-mono">{formatCedis(p.amount)}</span></li>)}</ul>
          <p className="mt-2 text-sm">{last.arrears_cleared ? "All arrears cleared — current bills are now open." : "Arrears remain; the oldest is settled first next time too."}</p>
        </section>
      )}
    </div>
  );
}

function split(pos: ArrearsPosition | undefined, amountStr: string) {
  if (!pos) return [];
  let remaining = Number(amountStr);
  if (!Number.isFinite(remaining) || remaining <= 0) return [];
  const out: { name: string; amount: number; current: boolean }[] = [];
  for (const o of [...pos.arrears.map((a) => ({ ...a, current: false })), ...pos.current_bills.map((b) => ({ ...b, current: true }))]) {
    if (remaining <= 0) break;
    const slice = Math.min(remaining, Number(o.balance));
    if (slice > 0) { out.push({ name: o.deceased_name, amount: Math.round(slice * 100) / 100, current: o.current }); remaining -= slice; }
  }
  return out;
}
