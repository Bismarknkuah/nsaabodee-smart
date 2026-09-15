"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { funeralsApi } from "@/lib/api/funerals";
import { useAuthStore } from "@/store/authStore";

/**
 * "If they paid but the system didn't reflect, the arrears collector
 * should edit but have to be approved by the community treasurer
 * before it reflects." The request itself is made from the Front
 * Desk page, right where a Community Arrears Officer, Family Arrears
 * Officer, or Town Elders Arrears Officer actually looks up someone's
 * arrears. This page is the other half: the Community Treasurer's
 * own approval queue, plus a full, permanent record of what was
 * decided and why.
 */
export default function ArrearsCorrectionsPage() {
  const qc = useQueryClient();
  const { data: corrections, isLoading } = useQuery({ queryKey: ["arrears-corrections"], queryFn: funeralsApi.listArrearsCorrections });
  const currentUser = useAuthStore((s) => s.user);

  // Matches funerals.services.ARREARS_CORRECTION_APPROVAL_ROLES exactly.
  // Deliberately narrower than payment reversal approval: this is
  // specifically the Treasurer's own call, not shared with Secretary
  // or Chairman.
  const canApprove = Boolean(
    currentUser?.is_superuser || currentUser?.role === "treasurer" || currentUser?.role === "community_admin"
  );

  const approve = useMutation({
    mutationFn: (id: string) => funeralsApi.approveArrearsCorrection(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["arrears-corrections"] }),
  });
  const reject = useMutation({
    mutationFn: (id: string) => funeralsApi.rejectArrearsCorrection(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["arrears-corrections"] }),
  });

  const pending = corrections?.filter((c) => c.status === "pending") ?? [];
  const decided = corrections?.filter((c) => c.status !== "pending") ?? [];

  return (
    <div className="font-body min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--text-soft)]">Financial Integrity</p>
        <h1 className="font-display mt-1 text-4xl">Arrears Corrections</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--text-soft)]">
          When a Community, Family, or Town Elders Arrears Officer believes a past payment was
          made but never reflected in the system, they can request a correction from the Front
          Desk. Nothing changes until a Community Treasurer reviews it here. Requests are sent
          from wherever an arrears officer looks up someone&apos;s outstanding balance.
        </p>
      </header>

      <main className="mx-auto max-w-3xl px-8 py-8">
        <section>
          <h2 className="font-display text-xl">Pending approval</h2>
          {isLoading ? (
            <p className="mt-2 text-sm text-[var(--text-soft)]">Loading…</p>
          ) : pending.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--text-soft)]">Nothing awaiting a decision.</p>
          ) : (
            <ul className="mt-3 space-y-3">
              {pending.map((c) => (
                <li key={c.id} className="rounded-sm border border-[var(--gold)] bg-[var(--gold-soft)] p-4">
                  <p className="text-sm font-medium">
                    {c.obligation_member_name} — {c.funeral_deceased_name}&apos;s funeral
                  </p>
                  <p className="mt-1 font-mono text-sm">GHS {c.amount} via {c.method}</p>
                  <p className="mt-1 text-sm">{c.reason}</p>
                  <p className="mt-2 text-xs text-[var(--text-soft)]">
                    Requested by {c.requested_by_username} on {new Date(c.requested_at).toLocaleDateString()}
                  </p>
                  {canApprove ? (
                    <div className="mt-2 flex gap-3">
                      <button onClick={() => approve.mutate(c.id)} className="text-sm font-medium" style={{ color: "var(--forest)" }}>
                        Approve
                      </button>
                      <button onClick={() => reject.mutate(c.id)} className="text-sm font-medium text-[var(--clay-red)]">
                        Reject
                      </button>
                    </div>
                  ) : (
                    <p className="mt-2 text-xs text-[var(--text-soft)]">Only the Community Treasurer can decide this.</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        {decided.length > 0 && (
          <section className="mt-8">
            <h2 className="font-display text-xl">Decided</h2>
            <ul className="mt-3 space-y-2">
              {decided.map((c) => (
                <li key={c.id} className="rounded-sm border border-[var(--border)] bg-white p-3 text-sm">
                  <span className={c.status === "approved" ? "font-medium" : "font-medium text-[var(--clay-red)]"} style={c.status === "approved" ? { color: "var(--forest)" } : undefined}>
                    {c.status === "approved" ? "Approved" : "Rejected"}
                  </span>
                  {" — "}{c.obligation_member_name}, GHS {c.amount} toward {c.funeral_deceased_name}&apos;s funeral
                  <p className="text-xs text-[var(--text-soft)]">
                    {c.requested_by_username} requested; {c.decided_by_username} decided on{" "}
                    {c.decided_at && new Date(c.decided_at).toLocaleDateString()}
                  </p>
                </li>
              ))}
            </ul>
          </section>
        )}
      </main>
    </div>
  );
}
