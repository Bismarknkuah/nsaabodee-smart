"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { welfareApi, type WelfareRequestRow } from "@/lib/api/welfare";
import { formatCedis } from "@/lib/formatCedis";

const STATUS_LABEL: Record<WelfareRequestRow["status"], string> = { pending: "Awaiting decision", approved: "Approved — awaiting payout", disbursed: "Paid out", rejected: "Declined" };
const STATUS_COLOR: Record<WelfareRequestRow["status"], string> = { pending: "var(--gold)", approved: "var(--violet)", disbursed: "var(--forest)", rejected: "var(--clay-red)" };

/**
 * The welfare request workflow, end to end: a member asks; the welfare manager (or whichever
 * officer administers that fund) approves or declines; a finance officer hands the money over;
 * the member confirms they received it. Three separations are enforced by the server, and shown
 * here as buttons that simply do not appear: nobody decides their own request; the person who
 * decides is never the one who pays out; only the requester can confirm receipt.
 */
export default function WelfareRequestsPage() {
  const qc = useQueryClient();
  const { data: rows, isLoading, error } = useQuery({ queryKey: ["welfare-requests"], queryFn: welfareApi.listRequests });
  const { data: campaigns } = useQuery({ queryKey: ["welfare-campaigns"], queryFn: welfareApi.listCampaigns });
  const [filter, setFilter] = useState<"all" | WelfareRequestRow["status"]>("all");
  const refresh = () => qc.invalidateQueries({ queryKey: ["welfare-requests"] });
  const decide = useMutation({ mutationFn: (v: { id: string; approve: boolean; amount?: string; reason?: string }) => welfareApi.decideRequest(v.id, { approve: v.approve, amount_approved: v.amount, rejection_reason: v.reason }), onSuccess: refresh });
  const disburse = useMutation({ mutationFn: (v: { id: string; amount?: string }) => welfareApi.disburseRequest(v.id, v.amount), onSuccess: refresh });
  const acknowledge = useMutation({ mutationFn: (id: string) => welfareApi.acknowledgeRequest(id), onSuccess: refresh });

  const [campaignId, setCampaignId] = useState(""); const [amount, setAmount] = useState(""); const [reason, setReason] = useState(""); const [info, setInfo] = useState("");
  const submit = useMutation({ mutationFn: () => welfareApi.submitRequest(campaignId, { amount_requested: amount, reason, supporting_info: info || undefined }), onSuccess: () => { setAmount(""); setReason(""); setInfo(""); refresh(); } });

  const all = rows ?? [];
  const shown = filter === "all" ? all : all.filter((r) => r.status === filter);
  const count = (s: WelfareRequestRow["status"]) => all.filter((r) => r.status === s).length;
  const card = "rounded-[var(--radius)] bg-[var(--card)] p-5";
  const cardStyle = { boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" } as const;
  const err = decide.error ?? disburse.error ?? acknowledge.error;

  return (
    <div className="font-body min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="border-b border-[var(--border)] bg-[var(--card)] px-8 py-6">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-soft)]">Welfare</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Welfare requests</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--text-soft)]">Ask for support from a fund, decide requests you administer, and confirm aid you have received.</p>
      </header>
      <main className="space-y-6 px-8 py-8">
        <section className={card} style={cardStyle}>
          <h2 className="text-lg font-semibold">Ask for support</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-3">
            <select value={campaignId} onChange={(e) => setCampaignId(e.target.value)} className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm"><option value="">Which fund?</option>{(campaigns ?? []).filter((c) => c.status === "active").map((c) => <option key={c.id} value={c.id}>{c.title}</option>)}</select>
            <input type="number" min="1" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Amount you need (GH₵)" className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm" />
            <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Why you need it" className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm" />
            <input value={info} onChange={(e) => setInfo(e.target.value)} placeholder="Anything that supports it (optional)" className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm sm:col-span-3" />
          </div>
          <div className="mt-3 flex items-center gap-3">
            <button onClick={() => submit.mutate()} disabled={!campaignId || !amount || !reason.trim() || submit.isPending} className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{submit.isPending ? "Sending…" : "Send request"}</button>
            {submit.isError && <span className="text-xs text-[var(--clay-red)]">{submit.error.message}</span>}
            {submit.isSuccess && <span className="text-xs" style={{ color: "var(--forest)" }}>Sent — you will see the decision here.</span>}
          </div>
        </section>

        <section className={card} style={cardStyle}>
          <div className="flex flex-wrap items-center gap-2">
            {(["all", "pending", "approved", "disbursed", "rejected"] as const).map((f) => (
              <button key={f} onClick={() => setFilter(f)} className={`rounded-lg px-3 py-1.5 text-sm font-medium ${filter === f ? "bg-[var(--primary)] text-white" : "border border-[var(--border)] hover:border-[var(--primary)]"}`}>{f === "all" ? "All" : STATUS_LABEL[f].split(" —")[0]} <span className="opacity-80">({f === "all" ? all.length : count(f)})</span></button>
            ))}
          </div>
          {isLoading && <p className="mt-3 text-sm text-[var(--text-soft)]">Loading…</p>}
          {error && <p className="mt-3 text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
          <ul className="mt-3 divide-y divide-[var(--border-soft)]">
            {shown.map((r) => (
              <li key={r.id} className="py-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-medium">{r.is_mine ? "You" : r.requester_name} <span className="font-normal text-[var(--text-soft)]">asked for</span> {formatCedis(r.amount_requested)} <span className="font-normal text-[var(--text-soft)]">from {r.campaign_title}{r.family_name ? ` (${r.family_name} family)` : ""}</span></p>
                    <p className="text-xs text-[var(--text-soft)]">{r.reason}{r.supporting_info ? ` — ${r.supporting_info}` : ""}</p>
                    <p className="mt-1 text-xs font-medium" style={{ color: STATUS_COLOR[r.status] }}>{STATUS_LABEL[r.status]}{r.amount_approved ? ` · approved ${formatCedis(r.amount_approved)}` : ""}{r.amount_disbursed ? ` · paid ${formatCedis(r.amount_disbursed)}` : ""}{r.acknowledged_at ? " · receipt confirmed" : ""}{r.status === "rejected" && r.rejection_reason ? ` · ${r.rejection_reason}` : ""}</p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {r.can_decide && (<>
                      <button onClick={() => { const a = window.prompt(`Approve how much? (they asked ${r.amount_requested})`, r.amount_requested); if (a) decide.mutate({ id: r.id, approve: true, amount: a }); }} className="rounded-lg bg-[var(--forest)] px-3 py-1.5 text-xs font-semibold text-white">Approve</button>
                      <button onClick={() => { const why = window.prompt("Why is this declined? (the requester will see it)"); if (why && why.trim()) decide.mutate({ id: r.id, approve: false, reason: why.trim() }); }} className="rounded-lg border border-[var(--clay-red)] px-3 py-1.5 text-xs font-semibold text-[var(--clay-red)]">Decline</button>
                    </>)}
                    {r.can_disburse && <button onClick={() => { if (window.confirm(`Confirm you have handed over ${formatCedis(r.amount_approved ?? r.amount_requested)} to ${r.requester_name}?`)) disburse.mutate({ id: r.id }); }} className="rounded-lg bg-[var(--primary)] px-3 py-1.5 text-xs font-semibold text-white">Mark paid out</button>}
                    {r.can_acknowledge && <button onClick={() => acknowledge.mutate(r.id)} className="rounded-lg bg-[var(--forest)] px-3 py-1.5 text-xs font-semibold text-white">I received this</button>}
                    {r.status === "approved" && !r.can_disburse && !r.can_decide && !r.is_mine && <span className="text-xs text-[var(--text-soft)]">With finance for payout</span>}
                  </div>
                </div>
              </li>
            ))}
            {shown.length === 0 && !isLoading && <li className="py-3 text-xs text-[var(--text-soft)]">Nothing here.</li>}
          </ul>
          {err && <p className="mt-2 text-xs text-[var(--clay-red)]">{err.message}</p>}
        </section>
      </main>
    </div>
  );
}
