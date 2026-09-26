"use client";

import { useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { membersApi } from "@/lib/api/members";
import { useFamilies } from "@/lib/hooks/useFamilies";
import { useAuthStore } from "@/store/authStore";
import { formatCedis } from "@/lib/formatCedis";

const MANAGE_ROLES = new Set(["community_admin", "chairman", "secretary", "community_registration_desk", "town_registration_officer"]);

/**
 * "When he clicks on someone's profile he should be able to see all
 * their details, the family they come from, how much they owe, and
 * more." Read from one endpoint that already applies the caller's
 * jurisdiction, so a family officer opening another family's member
 * gets a clean refusal rather than a half-rendered page.
 */
export function MemberProfilePanel({ memberId }: { memberId: string }) {
  const qc = useQueryClient();
  const role = useAuthStore((s) => s.user?.role);
  const canManage = Boolean(role && MANAGE_ROLES.has(role));
  const { data: p, isLoading, error } = useQuery({ queryKey: ["member-profile", memberId], queryFn: () => membersApi.profile(memberId) });
  const { data: families } = useFamilies();
  const [moveTo, setMoveTo] = useState("");
  const [reason, setReason] = useState("");
  const invalidate = () => { qc.invalidateQueries({ queryKey: ["member-profile", memberId] }); qc.invalidateQueries({ queryKey: ["member", memberId] }); qc.invalidateQueries({ queryKey: ["members"] }); };
  const move = useMutation({ mutationFn: () => membersApi.moveFamily(memberId, moveTo), onSuccess: () => { setMoveTo(""); invalidate(); } });
  const deactivate = useMutation({ mutationFn: () => membersApi.deactivate(memberId, reason), onSuccess: () => { setReason(""); invalidate(); } });
  const reactivate = useMutation({ mutationFn: () => membersApi.reactivateMember(memberId), onSuccess: invalidate });

  if (isLoading) return <p className="mt-6 text-sm text-[var(--text-soft)]">Loading full profile…</p>;
  if (error || !p) return <p className="mt-6 text-sm text-[var(--clay-red)]">{(error as Error)?.message ?? "Could not load profile."}</p>;
  const m = p.member;
  const owes = Number(p.total_owed) > 0;
  const card = "rounded-[var(--radius)] bg-[var(--card)] p-5";
  const cardStyle = { boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" } as const;

  return (
    <div className="mt-6 space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <div className={card} style={cardStyle}><p className="text-xs text-[var(--text-soft)]">Owes right now</p><p className="mt-1 text-2xl font-semibold" style={{ color: owes ? "var(--clay-red)" : "var(--forest)" }}>{formatCedis(p.total_owed)}</p></div>
        <div className={card} style={cardStyle}><p className="text-xs text-[var(--text-soft)]">Paid, all time</p><p className="mt-1 text-2xl font-semibold" style={{ color: "var(--forest)" }}>{formatCedis(p.paid_all_time)}</p></div>
        <div className={card} style={cardStyle}><p className="text-xs text-[var(--text-soft)]">Family</p><p className="mt-1 text-2xl font-semibold">{p.family ? <Link href={`/families`} className="hover:underline">{p.family.name}</Link> : "—"}</p></div>
      </div>

      <section className={card} style={cardStyle}>
        <h2 className="text-lg font-semibold">All details</h2>
        <dl className="mt-3 grid grid-cols-1 gap-x-6 gap-y-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
          {([["Membership no.", m.membership_number], ["Gender", m.gender], ["Date of birth", m.date_of_birth], ["Phone", m.phone], ["Email", m.email], ["Address", m.address], ["Hometown", m.hometown], ["Occupation", m.occupation], ["Marital status", m.marital_status], ["Spouse", m.spouse_name], ["Mother", m.mother_name], ["Father", m.father_name], ["Emergency contact", m.emergency_contact_name && `${m.emergency_contact_name} · ${m.emergency_contact_phone ?? ""}`], ["Seniority", m.family_seniority], ["Position in family", m.family_position], ["Town elder", m.is_town_leader ? `Yes${m.town_elder_title ? ` · ${m.town_elder_title}` : ""}` : "No"], ["Status", m.status], ["Defaulter tier", m.defaulter_tier], ["Registered", m.created_at && new Date(String(m.created_at)).toLocaleDateString()], ["Registered by", m.registered_by], ["Login", p.login ? `${p.login.username} · ${(p.login as { role_label?: string }).role_label ?? p.login.role}${p.login.is_active ? "" : " (suspended)"}` : "No login"]] as [string, unknown][]).map(([label, value]) => (
            <div key={label} className="flex justify-between gap-3 border-b border-[var(--border-soft)] py-1.5"><dt className="text-[var(--text-soft)]">{label}</dt><dd className="text-right font-medium">{value ? String(value) : "—"}</dd></div>
          ))}
        </dl>
      </section>

      <section className={card} style={cardStyle}>
        <h2 className="text-lg font-semibold">Every funeral obligation</h2>
        {p.obligations.length === 0 ? <p className="mt-2 text-sm text-[var(--text-soft)]">No obligations yet.</p> : (
          <table className="mt-3 w-full text-sm">
            <thead><tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wide text-[var(--text-soft)]"><th className="py-2 font-medium">Funeral</th><th className="py-2 text-right font-medium">Expected</th><th className="py-2 text-right font-medium">Paid</th><th className="py-2 text-right font-medium">Balance</th></tr></thead>
            <tbody className="divide-y divide-[var(--border-soft)]">
              {p.obligations.map((o) => (
                <tr key={o.funeral_id}>
                  <td className="py-2"><Link href={`/funerals/${o.funeral_id}`} className="font-medium hover:underline">{o.deceased_name}</Link><p className="text-xs text-[var(--text-soft)]">{o.funeral_status} · {o.rate_type.replace(/_/g, " ")}</p></td>
                  <td className="py-2 text-right font-mono">{formatCedis(o.expected_amount)}</td>
                  <td className="py-2 text-right font-mono" style={{ color: "var(--forest)" }}>{formatCedis(o.amount_paid)}</td>
                  <td className="py-2 text-right font-mono" style={{ color: Number(o.balance) > 0 ? "var(--clay-red)" : "var(--text-soft)" }}>{formatCedis(o.balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {p.recent_payments.length > 0 && (
          <>
            <h3 className="mt-5 text-sm font-semibold uppercase tracking-wide text-[var(--text-soft)]">Recent payments</h3>
            <ul className="mt-2 divide-y divide-[var(--border-soft)] text-sm">
              {p.recent_payments.map((pay, i) => (
                <li key={i} className="flex justify-between py-1.5"><span>{pay.deceased_name} · {pay.method}{pay.collector_name ? ` · ${pay.collector_name}` : ""}</span><span className="font-mono">{formatCedis(pay.amount)} <span className="text-xs text-[var(--text-soft)]">{new Date(pay.paid_at).toLocaleDateString()}</span></span></li>
              ))}
            </ul>
          </>
        )}
      </section>

      {canManage && (
        <section className={card} style={cardStyle}>
          <h2 className="text-lg font-semibold">Registrar actions</h2>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-soft)]">Move to another family</p>
              <p className="mt-1 text-xs text-[var(--text-soft)]">Past obligations stay under the family they were billed to; only future funerals bill under the new one.</p>
              <div className="mt-2 flex gap-2">
                <select value={moveTo} onChange={(e) => setMoveTo(e.target.value)} className="flex-1 rounded-lg border border-[var(--border)] px-3 py-2 text-sm">
                  <option value="">Choose family…</option>
                  {(families ?? []).filter((f) => f.id !== p.family?.id).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
                </select>
                <button onClick={() => move.mutate()} disabled={!moveTo || move.isPending} className="rounded-lg bg-[var(--primary)] px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">Move</button>
              </div>
              {move.isError && <p className="mt-1 text-xs text-[var(--clay-red)]">{move.error.message}</p>}
            </div>
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-soft)]">{m.status === "inactive" ? "Reactivate" : "Deactivate (remove from the register)"}</p>
              <p className="mt-1 text-xs text-[var(--text-soft)]">{m.status === "inactive" ? "Restores them to active and re-enables their login." : "Removes them from future funerals and suspends their login. Every past payment stays on the ledger."}</p>
              {m.status === "inactive" ? (
                <button onClick={() => reactivate.mutate()} disabled={reactivate.isPending} className="mt-2 rounded-lg px-3 py-2 text-sm font-semibold text-white" style={{ backgroundColor: "var(--forest)" }}>Reactivate</button>
              ) : (
                <div className="mt-2 flex gap-2">
                  <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason (kept on record)" className="flex-1 rounded-lg border border-[var(--border)] px-3 py-2 text-sm" />
                  <button onClick={() => { if (window.confirm(`Deactivate ${m.full_name}?`)) deactivate.mutate(); }} disabled={m.status === "deceased" || deactivate.isPending} className="rounded-lg px-3 py-2 text-sm font-semibold text-white disabled:opacity-50" style={{ backgroundColor: "var(--clay-red)" }}>Deactivate</button>
                </div>
              )}
              {(deactivate.isError || reactivate.isError) && <p className="mt-1 text-xs text-[var(--clay-red)]">{(deactivate.error ?? reactivate.error)?.message}</p>}
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
