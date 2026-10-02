"use client";

import "@/styles/family-registry-tokens.css";
import Link from "next/link";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api/dashboard";
import { welfareApi } from "@/lib/api/welfare";
import { formatCedis } from "@/lib/formatCedis";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";
import { KpiTile, SectionCard } from "@/components/dashboard/DashboardVisuals";
import { ContactActions } from "@/components/dashboard/CollectorParts";
import { IconMoney, IconPeople, IconWarning } from "@/components/icons/DashboardIcons";

interface Campaign { id: string; title: string; status: string; member_count: number; expected_total: string; collected_total: string; progress_pct: number; owing: { member_name: string; phone: string; balance: string }[] }
interface WelfareOverview {
  message?: string; level: "community" | "family"; family_id: string | null; family_name: string | null;
  campaigns: Campaign[]; campaign_count: number;
  pending_requests: { id: string; campaign_id: string; requester: string; campaign: string; amount_requested: string; reason: string }[]; pending_request_count: number;
  awaiting_disbursement: { id: string; requester: string; campaign: string; amount_approved: string }[]; awaiting_disbursement_count: number;
  approved_requests_count: number; approved_total: string; members_owing_count: number;
  categories: { id: string; name: string; amount_type: string; fixed_amount: string | null }[];
}

/**
 * The welfare manager's workspace — community-wide or one family's. Decide requests right here,
 * start a campaign, and see (and chase) who still owes on each. Never a payment form: collectors
 * take the money, and a finance officer hands aid over — whoever decides is never who pays.
 */
export default function WelfareManagerDashboardPage() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const ov = data?.sections?.welfare_manager_overview as WelfareOverview | undefined;
  const refresh = () => { qc.invalidateQueries({ queryKey: ["dashboard"] }); qc.invalidateQueries({ queryKey: ["welfare-requests"] }); };
  const decide = useMutation({ mutationFn: (v: { id: string; approve: boolean; amount?: string; reason?: string }) => welfareApi.decideRequest(v.id, { approve: v.approve, amount_approved: v.amount, rejection_reason: v.reason }), onSuccess: refresh });

  const [categoryId, setCategoryId] = useState(""); const [title, setTitle] = useState(""); const [amount, setAmount] = useState(""); const [due, setDue] = useState("");
  const start = useMutation({
    mutationFn: () => {
      const input = { category_id: categoryId, title: title.trim(), amount: amount || undefined, due_date: due || undefined };
      return ov?.level === "family" && ov.family_id ? welfareApi.initiateFamilyCampaign(ov.family_id, input) : welfareApi.initiateCommunityCampaign(input);
    },
    onSuccess: () => { setTitle(""); setAmount(""); setDue(""); refresh(); },
  });
  const register = ov?.level === "family" ? `${ov.family_name} family welfare` : "Community welfare";
  const card = "rounded-[var(--radius)] bg-[var(--card)] p-5"; const cardStyle = { boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" } as const;

  return (
    <DashboardPageShell folio="Folio IX" register={register} title="Welfare" subtitle={ov?.level === "family" ? "Your family's own campaigns and requests — nothing outside the family." : "The community's welfare campaigns and requests."}>
      {isLoading && <p className="text-sm text-[var(--text-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
      {ov?.message && <p className="text-sm text-[var(--text-soft)]">{ov.message}</p>}
      {ov && !ov.message && (
        <div className="lg:col-span-2 space-y-6">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <KpiTile label="Requests to decide" value={ov.pending_request_count} color={ov.pending_request_count > 0 ? "gold" : "forest"} icon={<IconWarning />} />
            <KpiTile label="Waiting on finance" value={ov.awaiting_disbursement_count} color="violet" icon={<IconMoney />} />
            <KpiTile label="Approved, all time" value={formatCedis(ov.approved_total)} color="forest" icon={<IconMoney />} />
            <KpiTile label="Members owing" value={ov.members_owing_count} color="clay" icon={<IconPeople />} />
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <SectionCard title="Requests to decide" eyebrow={`${ov.pending_request_count} pending — oldest first`} accent="gold">
              <ul className="divide-y divide-[var(--border-soft)]">
                {ov.pending_requests.map((r) => (
                  <li key={r.id} className="py-2.5 text-sm">
                    <div className="flex justify-between gap-2"><span className="font-medium">{r.requester}</span><span className="font-mono">{formatCedis(r.amount_requested)}</span></div>
                    <p className="text-xs text-[var(--text-soft)]">{r.campaign} · {r.reason}</p>
                    <div className="mt-1.5 flex gap-2">
                      <button onClick={() => { const a = window.prompt(`Approve how much? (asked ${r.amount_requested})`, r.amount_requested); if (a) decide.mutate({ id: r.id, approve: true, amount: a }); }} className="rounded-lg bg-[var(--forest)] px-3 py-1 text-xs font-semibold text-white">Approve</button>
                      <button onClick={() => { const why = window.prompt("Why is this declined? (the requester will see it)"); if (why && why.trim()) decide.mutate({ id: r.id, approve: false, reason: why.trim() }); }} className="rounded-lg border border-[var(--clay-red)] px-3 py-1 text-xs font-semibold text-[var(--clay-red)]">Decline</button>
                    </div>
                  </li>
                ))}
                {ov.pending_requests.length === 0 && <li className="py-2 text-xs text-[var(--text-soft)]">Nothing waiting.</li>}
              </ul>
              {decide.isError && <p className="mt-2 text-xs text-[var(--clay-red)]">{decide.error.message}</p>}
              <div className="mt-3 text-xs"><Link href="/welfare-requests" className="font-medium text-[var(--primary)] hover:underline">All requests, including yours →</Link></div>
            </SectionCard>

            <SectionCard title="Approved — waiting on finance" eyebrow="You approved; a finance officer hands the money over" accent="violet">
              <ul className="divide-y divide-[var(--border-soft)]">
                {ov.awaiting_disbursement.map((r) => <li key={r.id} className="flex justify-between py-2 text-sm"><span>{r.requester} <span className="text-xs text-[var(--text-soft)]">· {r.campaign}</span></span><span className="font-mono">{formatCedis(r.amount_approved)}</span></li>)}
                {ov.awaiting_disbursement.length === 0 && <li className="py-2 text-xs text-[var(--text-soft)]">Nothing waiting on payout.</li>}
              </ul>
            </SectionCard>
          </div>

          <section className={card} style={cardStyle}>
            <h2 className="text-lg font-semibold">Start a campaign</h2>
            <p className="mt-1 text-xs text-[var(--text-soft)]">{ov.level === "family" ? "A family campaign goes to your family's other executives for approval before anyone is billed." : "Members are billed as soon as the campaign starts."}</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-4">
              <select value={categoryId} onChange={(e) => { setCategoryId(e.target.value); const c = ov.categories.find((x) => x.id === e.target.value); if (c?.fixed_amount) setAmount(c.fixed_amount); }} className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm"><option value="">Category…</option>{ov.categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Campaign title" className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm" />
              <input type="number" min="0" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Amount each (GH₵)" className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm" />
              <input type="date" value={due} onChange={(e) => setDue(e.target.value)} className="rounded-lg border border-[var(--border)] px-3 py-2 text-sm" />
            </div>
            <div className="mt-3 flex items-center gap-3">
              <button onClick={() => { if (window.confirm(`Start "${title.trim()}"${amount ? ` at GH₵${amount} each` : ""}?`)) start.mutate(); }} disabled={!categoryId || !title.trim() || start.isPending} className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{start.isPending ? "Starting…" : "Start campaign"}</button>
              {start.isError && <span className="text-xs text-[var(--clay-red)]">{start.error.message}</span>}
              {ov.categories.length === 0 && <span className="text-xs text-[var(--text-soft)]">No category exists yet — an Admin creates categories under Welfare & Contributions.</span>}
            </div>
          </section>

          <SectionCard title="Campaigns" eyebrow="Progress, and who still owes — collectors take the money" accent="forest">
            <ul className="space-y-5">
              {ov.campaigns.map((c) => (
                <li key={c.id}>
                  <div className="flex items-baseline justify-between gap-2"><span className="text-sm font-medium">{c.title} <span className="text-xs font-normal text-[var(--text-soft)]">· {c.status.replace(/_/g, " ")} · {c.member_count} member(s)</span></span><span className="font-mono text-sm"><span style={{ color: "var(--forest)" }}>{formatCedis(c.collected_total)}</span><span className="text-xs text-[var(--text-soft)]"> / {formatCedis(c.expected_total)}</span></span></div>
                  <div className="mt-1 h-2 overflow-hidden rounded-full bg-[var(--bg)]"><div className="h-full rounded-full" style={{ width: `${Math.min(100, c.progress_pct)}%`, backgroundColor: "var(--forest)" }} /></div>
                  {c.owing.length > 0 && (
                    <ul className="mt-2 divide-y divide-[var(--border-soft)] rounded-lg border border-[var(--border-soft)] px-3">
                      {c.owing.map((o, i) => (
                        <li key={i} className="flex items-center justify-between gap-2 py-1.5 text-xs"><span>{o.member_name}{o.phone ? <span className="text-[var(--text-soft)]"> · {o.phone}</span> : null}</span><span className="flex items-center gap-3"><ContactActions row={{ member_id: o.member_name, member_name: o.member_name, phone: o.phone, total_owed: o.balance, purpose: c.title }} /><span className="font-mono" style={{ color: "var(--clay-red)" }}>{formatCedis(o.balance)}</span></span></li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
              {ov.campaigns.length === 0 && <li className="text-xs text-[var(--text-soft)]">No active campaign — start one above.</li>}
            </ul>
          </SectionCard>
        </div>
      )}
    </DashboardPageShell>
  );
}
