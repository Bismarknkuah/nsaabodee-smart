"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { reportsApi } from "@/lib/api/reports";
import { contributionRulesApi } from "@/lib/api/contributionRules";
import { membersApi } from "@/lib/api/members";
import { formatCedis } from "@/lib/formatCedis";
import { useAuthStore } from "@/store/authStore";

const TITLE_LABEL: Record<string, string> = {
  chief: "Chief",
  queen_mother: "Queen Mother",
  linguist: "Linguist",
  other: "Other Town Executive",
};

/**
 * 'They should also be registered as town elders which consist of the
 * chief, queen mother, linguist, and other town executive... the
 * community ledger is for all community members excluding town
 * elders who have their own ledger and they pay higher than all the
 * member... the town leader/king is the head of the community's
 * elders ledger.'
 */
export default function TownEldersLedgerPage() {
  const currentUser = useAuthStore((s) => s.user);
  const isChief = currentUser?.role === "traditional_leader";
  // Matches the backend's own _TOWN_ELDER_TRANSFER_ROLES exactly —
  // 'the town leader should also have user management... to manage
  // the town elders ledger' extended the chief into the same set
  // that already includes Community Admin/Chairman/Secretary.
  const canManageMembership = Boolean(
    currentUser?.is_superuser || ["community_admin", "chairman", "secretary", "traditional_leader"].includes(currentUser?.role ?? "")
  );
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["town-elders-ledger"], queryFn: reportsApi.townEldersLedger });
  const [newRate, setNewRate] = useState("");

  const removeFromTownElder = useMutation({
    mutationFn: (memberId: string) => membersApi.removeFromTownElder(memberId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["town-elders-ledger"] }),
  });

  const setRate = useMutation({
    mutationFn: (amount: string) => contributionRulesApi.setTownElderRate(amount),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["town-elders-ledger"] });
      setNewRate("");
    },
  });

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
          A separate ledger, out of respect for the town's leadership
        </p>
        <h1 className="font-display mt-1 text-4xl">Town Elders Ledger</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Chiefs, queen mothers, linguists, and other town executives — never part of the
          community's ordinary ledger, and paying at their own, higher rate.
        </p>
      </header>

      <main className="px-8 py-8">
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
        {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}

        {data && (
          <>
            <div className="mb-6 flex flex-wrap items-end justify-between gap-4 border-b border-[var(--rule)] pb-6">
              <div>
                <p className="text-xs text-[var(--ink-soft)]">Current rate per funeral</p>
                <p className="font-display text-3xl" style={{ color: "var(--forest)" }}>{formatCedis(data.current_rate)}</p>
              </div>

              {isChief && (
                <form
                  onSubmit={(e) => { e.preventDefault(); if (newRate) setRate.mutate(newRate); }}
                  className="flex items-end gap-2"
                >
                  <div>
                    <label className="block text-xs font-medium text-[var(--ink-soft)]">Set a new rate (only you can do this)</label>
                    <input
                      type="number" min="1" step="0.01" value={newRate}
                      onChange={(e) => setNewRate(e.target.value)}
                      placeholder="e.g. 150"
                      className="mt-1 w-32 rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={setRate.isPending || !newRate}
                    className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
                  >
                    {setRate.isPending ? "Saving…" : "Set rate"}
                  </button>
                </form>
              )}
            </div>
            {setRate.isError && <p className="mb-4 text-sm text-[var(--clay-red)]">{setRate.error.message}</p>}
            {removeFromTownElder.isError && <p className="mb-4 text-sm text-[var(--clay-red)]">{removeFromTownElder.error.message}</p>}

            <p className="mb-3 font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
              {data.town_elder_count} town elder(s)
            </p>

            {data.members.length === 0 && (
              <p className="text-sm text-[var(--ink-soft)]">No one has been transferred to the Town Elders ledger yet.</p>
            )}

            <ol className="divide-y divide-[var(--rule)] border-y-2 border-[var(--ink)]">
              {data.members.map((m) => (
                <li key={m.member_id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium">{m.member_name}</p>
                    <p className="text-xs text-[var(--ink-soft)]">
                      {m.title ? TITLE_LABEL[m.title] ?? m.title : "—"} · {m.funeral_count} funeral(s)
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-right">
                      <p className="font-mono text-sm">{formatCedis(m.collected_total)} <span className="text-[var(--ink-soft)]">/ {formatCedis(m.expected_total)}</span></p>
                      {Number(m.outstanding_total) > 0 && (
                        <p className="text-xs text-[var(--clay-red)]">{formatCedis(m.outstanding_total)} outstanding</p>
                      )}
                    </div>
                    {canManageMembership && (
                      <button
                        onClick={() => {
                          if (confirm(`Remove ${m.member_name} from the Town Elders ledger? They'll go back to their family's ordinary rate on any NEW funeral opened after this.`)) {
                            removeFromTownElder.mutate(m.member_id);
                          }
                        }}
                        disabled={removeFromTownElder.isPending}
                        className="shrink-0 rounded-sm border border-[var(--clay-red)] px-2 py-1 text-xs text-[var(--clay-red)] disabled:opacity-50"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </>
        )}
      </main>
    </div>
  );
}
