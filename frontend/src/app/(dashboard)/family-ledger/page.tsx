"use client";

import "@/styles/family-registry-tokens.css";
import Link from "next/link";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { reportsApi, type FamilyFuneralLedger } from "@/lib/api/reports";
import { useFamilies } from "@/lib/hooks/useFamilies";
import { useAuthStore } from "@/store/authStore";
import { formatCedis } from "@/lib/formatCedis";

const OVERSIGHT = ["community_admin", "chairman", "secretary", "financial_secretary", "treasurer", "auditor"];

/**
 * 'Each family secretary and collector should have the ledger button in the task menu, limited to his family's
 * members.' The family's own funeral-contribution ledger: every member billed on it, what they were billed, what they
 * paid, what they owe. A member moved to the Town Elders ledger pays the elders, not the family, and is not here.
 * A family officer or family collector is confined to their own family on the server; community oversight picks one.
 */
export default function FamilyLedgerPage() {
  const user = useAuthStore((s) => s.user);
  const isOversight = Boolean(user?.is_superuser || OVERSIGHT.includes(user?.role ?? ""));
  const { data: families } = useFamilies(isOversight);
  const [chosen, setChosen] = useState("");
  const familyId = isOversight ? chosen || families?.[0]?.id : undefined;
  const { data, isLoading, error } = useQuery({
    queryKey: ["family-ledger", familyId ?? "own"],
    queryFn: () => reportsApi.familyLedger(familyId),
    enabled: !isOversight || Boolean(familyId),
  });

  return (
    <div className="font-body min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="border-b border-[var(--border)] bg-[var(--card)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--text-soft)]">The family's own ledger</p>
        <h1 className="font-display mt-1 text-4xl">{data ? `${data.family_name} Family Ledger` : "Family Ledger"}</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--text-soft)]">
          Every member who pays into this family's ledger, with what they were billed across every funeral, what they paid, and what they still owe.
          A member moved to the Town Elders ledger pays the elders instead and is not listed here.
        </p>
        {isOversight && families && families.length > 0 && (
          <select value={familyId ?? ""} onChange={(e) => setChosen(e.target.value)} className="mt-3 rounded-lg border border-[var(--border)] bg-white px-3 py-1.5 text-sm">
            {families.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
        )}
      </header>
      <main className="px-8 py-8">
        {isLoading && <p className="text-sm text-[var(--text-soft)]">Loading…</p>}
        {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
        {data && (
          <>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              {[["Members on this ledger", String(data.member_count)], ["Still owing", String(data.members_owing_count)], ["Collected", formatCedis(data.collected_total)], ["Outstanding", formatCedis(data.outstanding_total)]].map(([label, value]) => (
                <div key={label} className="rounded-[var(--radius)] bg-[var(--card)] p-4" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
                  <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-soft)]">{label}</p>
                  <p className="mt-1 text-2xl font-semibold">{value}</p>
                </div>
              ))}
            </div>
            <FuneralsSection funerals={data.funerals} familyId={isOversight ? familyId : undefined} />

            <h2 className="mt-8 text-lg font-semibold">By member</h2>
            <div className="mt-3 overflow-x-auto rounded-[var(--radius)] bg-[var(--card)]" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wide text-[var(--text-soft)]">
                    <th className="px-4 py-3 font-medium">Member</th><th className="px-4 py-3 font-medium">Funerals</th><th className="px-4 py-3 text-right font-medium">Billed</th><th className="px-4 py-3 text-right font-medium">Paid</th><th className="px-4 py-3 text-right font-medium">Owes</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border-soft)]">
                  {data.members.map((m) => (
                    <tr key={m.member_id}>
                      <td className="px-4 py-2.5"><Link href={`/members/${m.member_id}`} className="font-medium hover:underline">{m.member_name}</Link>{m.phone && <a href={`tel:${m.phone}`} className="ml-2 text-xs text-[var(--primary)] hover:underline">{m.phone}</a>}</td>
                      <td className="px-4 py-2.5 text-[var(--text-soft)]">{m.funeral_count}</td>
                      <td className="px-4 py-2.5 text-right font-mono">{formatCedis(m.expected_total)}</td>
                      <td className="px-4 py-2.5 text-right font-mono" style={{ color: "var(--forest)" }}>{formatCedis(m.collected_total)}</td>
                      <td className="px-4 py-2.5 text-right font-mono" style={{ color: Number(m.outstanding_total) > 0 ? "var(--clay-red)" : "var(--text-soft)" }}>{formatCedis(m.outstanding_total)}</td>
                    </tr>
                  ))}
                  {data.members.length === 0 && <tr><td colSpan={5} className="px-4 py-4 text-xs text-[var(--text-soft)]">Nobody has been billed on this ledger yet.</td></tr>}
                </tbody>
              </table>
            </div>
          </>
        )}
      </main>
    </div>
  );
}


const TYPE_LABEL: Record<string, string> = { contributions: "Funeral contributions", asupede: "Asupedeɛ" };

/** 'After each funeral the details of the ledger should be seen.' Every funeral in the family's ledger; open one for the member-by-member, payment-by-payment detail. */
function FuneralsSection({ funerals, familyId }: { funerals: { funeral_id: string; deceased_name: string; funeral_type: string; status: string; collection_start_date: string; member_count: number; expected_total: string; collected_total: string; outstanding_total: string }[]; familyId?: string }) {
  const [open, setOpen] = useState<string | null>(null);
  const { data: detail, isLoading } = useQuery({ queryKey: ["family-funeral-ledger", open, familyId ?? "own"], queryFn: () => reportsApi.familyFuneralLedger(open!, familyId), enabled: Boolean(open) });
  return (
    <>
      <h2 className="mt-8 text-lg font-semibold">By funeral</h2>
      <div className="mt-3 overflow-x-auto rounded-[var(--radius)] bg-[var(--card)]" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
        <table className="w-full text-sm">
          <thead><tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wide text-[var(--text-soft)]"><th className="px-4 py-3 font-medium">Funeral</th><th className="px-4 py-3 font-medium">Type</th><th className="px-4 py-3 font-medium">Status</th><th className="px-4 py-3 text-right font-medium">Billed</th><th className="px-4 py-3 text-right font-medium">Paid</th><th className="px-4 py-3 text-right font-medium">Owes</th></tr></thead>
          <tbody className="divide-y divide-[var(--border-soft)]">
            {funerals.map((f) => (
              <tr key={f.funeral_id} className="cursor-pointer hover:bg-[var(--bg)]" onClick={() => setOpen(open === f.funeral_id ? null : f.funeral_id)}>
                <td className="px-4 py-2.5"><span className="font-medium">{f.deceased_name}</span><span className="ml-2 text-xs text-[var(--text-soft)]">{new Date(f.collection_start_date).toLocaleDateString()} · {f.member_count} member(s) {open === f.funeral_id ? "▴" : "▾"}</span></td>
                <td className="px-4 py-2.5 text-[var(--text-soft)]">{TYPE_LABEL[f.funeral_type] ?? f.funeral_type}</td>
                <td className="px-4 py-2.5 text-[var(--text-soft)]">{f.status}</td>
                <td className="px-4 py-2.5 text-right font-mono">{formatCedis(f.expected_total)}</td>
                <td className="px-4 py-2.5 text-right font-mono" style={{ color: "var(--forest)" }}>{formatCedis(f.collected_total)}</td>
                <td className="px-4 py-2.5 text-right font-mono" style={{ color: Number(f.outstanding_total) > 0 ? "var(--clay-red)" : "var(--text-soft)" }}>{formatCedis(f.outstanding_total)}</td>
              </tr>
            ))}
            {funerals.length === 0 && <tr><td colSpan={6} className="px-4 py-4 text-xs text-[var(--text-soft)]">No funeral has billed this family yet.</td></tr>}
          </tbody>
        </table>
      </div>
      {open && (
        <div className="mt-3 rounded-[var(--radius)] bg-[var(--card)] p-4" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
          {isLoading && <p className="text-sm text-[var(--text-soft)]">Loading…</p>}
          {detail && <FuneralDetail detail={detail} />}
        </div>
      )}
    </>
  );
}

function FuneralDetail({ detail }: { detail: FamilyFuneralLedger }) {
  return (
    <>
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-soft)]">{detail.funeral.deceased_name} · {TYPE_LABEL[detail.funeral.funeral_type] ?? detail.funeral.funeral_type} · {detail.funeral.status}</p>
      <p className="mt-1 text-sm">Billed {formatCedis(detail.expected_total)} · paid <span style={{ color: "var(--forest)" }}>{formatCedis(detail.collected_total)}</span> · owing <span style={{ color: "var(--clay-red)" }}>{formatCedis(detail.outstanding_total)}</span> ({detail.members_owing_count} member(s))</p>
      <ul className="mt-3 divide-y divide-[var(--border-soft)]">
        {detail.members.map((m) => (
          <li key={m.member_id} className="py-2 text-sm">
            <div className="flex items-center justify-between"><Link href={`/members/${m.member_id}`} className="font-medium hover:underline">{m.member_name}</Link><span className="font-mono">{formatCedis(m.amount_paid)} / {formatCedis(m.expected_amount)}{Number(m.balance) > 0 && <span className="ml-2 text-xs" style={{ color: "var(--clay-red)" }}>owes {formatCedis(m.balance)}</span>}</span></div>
            {m.payments.length > 0 && <p className="mt-0.5 text-xs text-[var(--text-soft)]">{m.payments.map((p) => `${formatCedis(p.amount)} ${p.method} on ${new Date(p.paid_at).toLocaleDateString()}${p.collected_by ? ` by ${p.collected_by}` : ""}`).join(" · ")}</p>}
          </li>
        ))}
      </ul>
      {detail.asupede.length > 0 && (
        <>
          <p className="mt-4 text-xs font-medium uppercase tracking-wide text-[var(--text-soft)]">Asupedeɛ · {formatCedis(detail.asupede_collected_total)} of {formatCedis(detail.asupede_expected_total)}</p>
          <ul className="mt-1 divide-y divide-[var(--border-soft)]">{detail.asupede.map((a) => <li key={a.member_id} className="flex justify-between py-1.5 text-sm"><span>{a.member_name}</span><span className="font-mono">{formatCedis(a.amount_paid)} / {formatCedis(a.expected_amount)}</span></li>)}</ul>
        </>
      )}
    </>
  );
}
