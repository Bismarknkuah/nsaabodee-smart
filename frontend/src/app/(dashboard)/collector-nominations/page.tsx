"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { collectorNominationsApi, type CollectorNomination } from "@/lib/api/members";
import { useMembers } from "@/lib/hooks/useMembers";
import { useAuthStore } from "@/store/authStore";

const TYPE_LABEL: Record<CollectorNomination["collector_type"], string> = {
  general: "General Collector (community ledger)",
  family: "Family Collector (family ledger)",
  donation: "Donation Collector (gift ledger)",
  town_elder: "Town Elders Collector",
};

// Who may nominate each type — mirrors members.services.COLLECTOR_NOMINATION_ROLES exactly.
const NOMINATOR_ROLES: Record<CollectorNomination["collector_type"], string[]> = {
  general: ["chairman", "community_admin"],
  family: ["family_head"],
  donation: ["family_head"],
  town_elder: ["traditional_leader"],
};

// Mirrors members.services.COLLECTOR_APPROVAL_RULES for display only — the backend is the real authority.
const APPROVAL_DESCRIPTION: Record<CollectorNomination["collector_type"], string> = {
  general: "Needs the Treasurer, plus either the Secretary or Chairman",
  family: "Needs the family's own Treasurer and Secretary",
  donation: "Needs the family's own Treasurer and Secretary",
  town_elder: "Needs two other community executives",
};

/**
 * 'For transparency, when one creates an account he needs other
 * executives to approve it before that account can start collecting
 * money.'
 */
export default function CollectorNominationsPage() {
  const currentUser = useAuthStore((s) => s.user);
  const qc = useQueryClient();
  const { data: nominations, isLoading, error } = useQuery({ queryKey: ["collector-nominations"], queryFn: collectorNominationsApi.list });
  const [showForm, setShowForm] = useState(false);

  const decide = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: "approve" | "reject" }) => collectorNominationsApi.decide(id, decision),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["collector-nominations"] }),
  });

  const nominatableTypes = (Object.keys(NOMINATOR_ROLES) as CollectorNomination["collector_type"][]).filter((t) =>
    NOMINATOR_ROLES[t].includes(currentUser?.role ?? "")
  );

  const pending = nominations?.filter((n) => n.status === "pending") ?? [];
  const decided = nominations?.filter((n) => n.status !== "pending") ?? [];

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
          Four categories, each its own creator and its own approvers
        </p>
        <div className="mt-1 flex items-start justify-between gap-4">
          <div>
            <h1 className="font-display text-4xl">Collector Nominations</h1>
            <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
              No new collector can start collecting money the moment they're nominated — every
              category needs its own set of executives to confirm first.
            </p>
          </div>
          {nominatableTypes.length > 0 && (
            <button onClick={() => setShowForm((s) => !s)} className="shrink-0 bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white">
              {showForm ? "Cancel" : "Nominate a collector"}
            </button>
          )}
        </div>
      </header>

      <main className="px-8 py-8">
        {showForm && <NominateForm nominatableTypes={nominatableTypes} onDone={() => setShowForm(false)} />}

        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
        {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}

        {pending.length > 0 && (
          <>
            <p className="mb-3 font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
              Awaiting approval · {pending.length}
            </p>
            <ol className="mb-8 divide-y divide-[var(--rule)] border-y-2 border-[var(--gold)]">
              {pending.map((n) => (
                <li key={n.id} className="py-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium">{n.member_name}</p>
                      <p className="text-xs text-[var(--ink-soft)]">
                        {TYPE_LABEL[n.collector_type]}{n.scoped_family_name && ` · ${n.scoped_family_name}`}
                      </p>
                      <p className="mt-1 text-xs text-[var(--ink-soft)]">
                        Nominated by {n.nominated_by ?? "—"} · {APPROVAL_DESCRIPTION[n.collector_type]}
                      </p>
                      {n.approvals.length > 0 && (
                        <p className="mt-1 text-xs" style={{ color: "var(--forest)" }}>
                          Already approved by: {n.approvals.filter((a) => a.decision === "approve").map((a) => a.decided_by).join(", ")}
                        </p>
                      )}
                    </div>
                    <div className="flex shrink-0 gap-2">
                      <button
                        onClick={() => decide.mutate({ id: n.id, decision: "approve" })}
                        disabled={decide.isPending}
                        className="rounded-sm border border-[var(--forest)] px-3 py-1.5 text-xs text-[var(--forest)] disabled:opacity-50"
                      >
                        Approve
                      </button>
                      <button
                        onClick={() => decide.mutate({ id: n.id, decision: "reject" })}
                        disabled={decide.isPending}
                        className="rounded-sm border border-[var(--clay-red)] px-3 py-1.5 text-xs text-[var(--clay-red)] disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </div>
                  </div>
                </li>
              ))}
            </ol>
          </>
        )}
        {decide.isError && <p className="mb-4 text-sm text-[var(--clay-red)]">{decide.error.message}</p>}

        {decided.length > 0 && (
          <>
            <p className="mb-3 font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Decided</p>
            <ol className="divide-y divide-[var(--rule)] border-y-2 border-[var(--ink)]">
              {decided.map((n) => (
                <li key={n.id} className="flex items-center justify-between py-3">
                  <div>
                    <p className="text-sm font-medium">{n.member_name}</p>
                    <p className="text-xs text-[var(--ink-soft)]">{TYPE_LABEL[n.collector_type]}</p>
                  </div>
                  <span
                    className="text-xs font-medium"
                    style={{ color: n.status === "approved" ? "var(--forest)" : "var(--clay-red)" }}
                  >
                    {n.status}
                  </span>
                </li>
              ))}
            </ol>
          </>
        )}
      </main>
    </div>
  );
}

function NominateForm({ nominatableTypes, onDone }: { nominatableTypes: CollectorNomination["collector_type"][]; onDone: () => void }) {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [memberId, setMemberId] = useState("");
  const [collectorType, setCollectorType] = useState<CollectorNomination["collector_type"]>(nominatableTypes[0]);
  const { data: members } = useMembers({ search });

  const nominate = useMutation({
    mutationFn: () => collectorNominationsApi.nominate(memberId, collectorType),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["collector-nominations"] });
      onDone();
    },
  });

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); if (memberId) nominate.mutate(); }}
      className="mb-8 grid gap-3 rounded-sm bg-[var(--surface)] p-4 sm:grid-cols-3"
    >
      <div>
        <label className="block text-xs font-medium text-[var(--ink-soft)]">Category</label>
        <select
          value={collectorType}
          onChange={(e) => setCollectorType(e.target.value as CollectorNomination["collector_type"])}
          className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
        >
          {nominatableTypes.map((t) => (
            <option key={t} value={t}>{TYPE_LABEL[t]}</option>
          ))}
        </select>
      </div>
      <div className="sm:col-span-2">
        <label className="block text-xs font-medium text-[var(--ink-soft)]">Search for a member</label>
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Name, phone, or Ghana Card…"
          className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
        />
        {members && members.length > 0 && search.trim().length >= 2 && (
          <ul className="mt-1 max-h-40 overflow-y-auto rounded-sm border border-[var(--rule)] bg-white">
            {members.slice(0, 8).map((m) => (
              <li key={m.id}>
                <button
                  type="button"
                  onClick={() => { setMemberId(m.id); setSearch(m.full_name); }}
                  className={`w-full px-3 py-2 text-left text-sm hover:bg-[var(--surface)] ${memberId === m.id ? "bg-[var(--surface)] font-medium" : ""}`}
                >
                  {m.full_name}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      {nominate.isError && <p className="text-sm text-[var(--clay-red)] sm:col-span-3">{nominate.error.message}</p>}
      <button
        type="submit"
        disabled={nominate.isPending || !memberId}
        className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60 sm:col-span-3"
      >
        {nominate.isPending ? "Nominating…" : "Nominate"}
      </button>
    </form>
  );
}
