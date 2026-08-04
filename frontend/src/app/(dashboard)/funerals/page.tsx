"use client";

import "@/styles/family-registry-tokens.css";
import Link from "next/link";
import { useState } from "react";
import { useFunerals, useFuneralApprovalProgress, useFuneralOpeningActions } from "@/lib/hooks/useFunerals";
import { useFuneralSummary } from "@/lib/hooks/useFunerals";
import { crestColorFor } from "@/lib/familyCrest";
import { formatCedis } from "@/lib/formatCedis";
import type { FuneralEvent } from "@/types/funeral";
import { CreateFuneralDialog } from "@/components/funerals/CreateFuneralDialog";
import { RequestFuneralOpeningDialog } from "@/components/funerals/RequestFuneralOpeningDialog";
import { MemberRateOverridesPanel } from "@/components/funerals/MemberRateOverridesPanel";
import { DeskAssignmentsPanel } from "@/components/funerals/DeskAssignmentsPanel";

export default function FuneralsListPage() {
  const [tab, setTab] = useState<"pending_approval" | "active" | "closed">("active");
  const { data: funerals, isLoading } = useFunerals(tab);
  const [showCreate, setShowCreate] = useState(false);
  const [showRequest, setShowRequest] = useState(false);

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-6 py-6 sm:px-10">
        <div className="mx-auto max-w-6xl">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
                Funeral Register
              </p>
              <h1 className="font-display mt-1 text-4xl">Funerals</h1>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setShowRequest(true)}
                className="border border-[var(--forest)] px-4 py-2 text-sm font-medium text-[var(--forest)] hover:bg-[var(--forest)] hover:text-white"
              >
                Request an opening
              </button>
              <button
                onClick={() => setShowCreate(true)}
                className="bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
              >
                Record a funeral directly
              </button>
            </div>
          </div>
          <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
            Every funeral has its own ledger. If several are running at the same time, each
            entry below shows its own totals only — nothing here is ever added across funerals.
            A Family Head&apos;s own request needs two approvals before anyone is billed.
          </p>
        </div>
      </header>

      <div className="mx-auto flex max-w-6xl gap-1 border-b border-[var(--rule)] px-6 py-3 sm:px-10">
        {(["pending_approval", "active", "closed"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 font-mono text-xs font-medium uppercase tracking-wide ${
              tab === t ? "bg-[var(--ink)] text-white" : "text-[var(--ink-soft)] hover:bg-[var(--surface)]"
            }`}
          >
            {t === "pending_approval" ? "Awaiting approval" : t === "active" ? "Currently collecting" : "Closed"}
          </button>
        ))}
      </div>

      <main className="mx-auto grid max-w-6xl gap-4 px-6 py-6 sm:grid-cols-2 sm:px-10 xl:grid-cols-3">
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading funerals…</p>}
        {!isLoading && funerals?.length === 0 && (
          <div className="col-span-full border border-dashed border-[var(--rule)] px-6 py-10 text-center">
            <p className="font-display text-lg">
              {tab === "pending_approval"
                ? "Nothing waiting on approval"
                : tab === "active"
                ? "No funerals are currently collecting"
                : "No closed funerals yet"}
            </p>
          </div>
        )}
        {tab === "pending_approval"
          ? funerals?.map((f) => <PendingFuneralCard key={f.id} funeral={f} />)
          : funerals?.map((f) => <FuneralCard key={f.id} funeral={f} />)}
      </main>

      {showCreate && <CreateFuneralDialog onClose={() => setShowCreate(false)} />}
      {showRequest && <RequestFuneralOpeningDialog onClose={() => setShowRequest(false)} />}
    </div>
  );
}

function PendingFuneralCard({ funeral }: { funeral: FuneralEvent }) {
  const { data: progress } = useFuneralApprovalProgress(funeral.id);
  const { approve, reject } = useFuneralOpeningActions(funeral.id);

  return (
    <div className="border-2 border-dashed border-[var(--gold)] bg-white p-5">
      <div className="flex items-start gap-3">
        <span aria-hidden className="mt-1 h-10 w-1.5 shrink-0 rounded-full" style={{ backgroundColor: crestColorFor(funeral.deceased_family) }} />
        <div className="min-w-0 flex-1">
          <h2 className="font-display truncate text-lg">{funeral.deceased_name}</h2>
          <p className="font-mono text-xs text-[var(--ink-soft)]">
            {funeral.deceased_family_name} family &middot; d. {new Date(funeral.date_of_death).toLocaleDateString()}
          </p>

          <MemberRateOverridesPanel funeralId={funeral.id} deceasedFamilyId={funeral.deceased_family} />
          <DeskAssignmentsPanel funeralId={funeral.id} />

          {progress && (
            <div className="mt-3">
              <p className="text-xs font-medium" style={{ color: "var(--gold)" }}>
                {progress.approval_count} of {progress.required_approvals} approvals — {progress.still_needed} more needed
              </p>
              {progress.approvals.length > 0 && (
                <ul className="mt-1 text-xs text-[var(--ink-soft)]">
                  {progress.approvals.map((a) => (
                    <li key={a.approved_by}>✓ {a.approved_by}</li>
                  ))}
                </ul>
              )}
            </div>
          )}

          <div className="mt-4 flex gap-2">
            <button
              onClick={() => approve.mutate()}
              disabled={approve.isPending}
              className="rounded-sm bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
            >
              {approve.isPending ? "Approving…" : "Approve"}
            </button>
            <button
              onClick={() => reject.mutate()}
              disabled={reject.isPending}
              className="rounded-sm border border-[var(--rule)] px-3 py-1.5 text-xs font-medium hover:border-[var(--clay-red)] hover:text-[var(--clay-red)]"
            >
              Reject
            </button>
          </div>
          {(approve.isError || reject.isError) && (
            <p className="mt-2 text-xs text-[var(--clay-red)]">
              {(approve.error as Error)?.message ?? (reject.error as Error)?.message}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function FuneralCard({ funeral }: { funeral: FuneralEvent }) {
  const { data: summary } = useFuneralSummary(funeral.id);
  const expected = summary ? Number(summary.own_family.expected_total) + Number(summary.general.expected_total) : 0;
  const collected = summary ? Number(summary.own_family.collected_total) + Number(summary.general.collected_total) : 0;
  const pct = expected > 0 ? Math.round((collected / expected) * 100) : 0;

  return (
    <Link
      href={`/funerals/${funeral.id}`}
      className="block border border-[var(--rule)] bg-white p-5 transition-shadow hover:shadow-md"
    >
      <div className="flex items-start gap-3">
        <span
          aria-hidden
          className="mt-1 h-10 w-1.5 shrink-0 rounded-full"
          style={{ backgroundColor: crestColorFor(funeral.deceased_family) }}
        />
        <div className="min-w-0 flex-1">
          <h2 className="font-display truncate text-lg">{funeral.deceased_name}</h2>
          <p className="font-mono text-xs text-[var(--ink-soft)]">
            {funeral.deceased_family_name} family &middot; d.{" "}
            {new Date(funeral.date_of_death).toLocaleDateString()}
          </p>

          <div className="mt-4 space-y-1 text-xs text-[var(--ink-soft)]">
            <div className="flex justify-between">
              <span>Own family rate ({funeral.deceased_family_name})</span>
              <span className="font-mono">{formatCedis(funeral.own_family_amount)}</span>
            </div>
            <div className="flex justify-between">
              <span>General rate — male</span>
              <span className="font-mono">{formatCedis(funeral.general_male_amount)}</span>
            </div>
            <div className="flex justify-between">
              <span>General rate — female</span>
              <span className="font-mono">{formatCedis(funeral.general_female_amount)}</span>
            </div>
          </div>

          {summary && (
            <div className="mt-4">
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface)]">
                <div className="h-full bg-[var(--forest)]" style={{ width: `${Math.min(pct, 100)}%` }} />
              </div>
              <p className="mt-1 font-mono text-xs text-[var(--ink-soft)]">
                {formatCedis(collected)} of {formatCedis(expected)} collected ({pct}%)
              </p>
            </div>
          )}
        </div>
      </div>
    </Link>
  );
}
