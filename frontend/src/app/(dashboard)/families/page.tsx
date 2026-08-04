"use client";

import "@/styles/family-registry-tokens.css";
import { useMemo, useState } from "react";
import { useFamilies } from "@/lib/hooks/useFamilies";
import { useFamilyUiStore } from "@/store/familyUiStore";
import { crestColorFor } from "@/lib/familyCrest";
import type { Family } from "@/types/family";
import { AddFamilyDialog } from "@/components/families/AddFamilyDialog";
import { RenameFamilyDialog } from "@/components/families/RenameFamilyDialog";
import { MergeFamilyDialog } from "@/components/families/MergeFamilyDialog";
import { DeactivateFamilyDialog } from "@/components/families/DeactivateFamilyDialog";
import { DeleteFamilyDialog } from "@/components/families/DeleteFamilyDialog";
import { TransferMembersDialog } from "@/components/families/TransferMembersDialog";
import { FamilyHistoryDrawer } from "@/components/families/FamilyHistoryDrawer";
import { FamilyRateDialog } from "@/components/families/FamilyRateDialog";
import { formatCedis } from "@/lib/formatCedis";

const STATUS_LABEL: Record<Family["status"], string> = {
  active: "Active",
  deactivated: "Deactivated",
  merged: "Merged",
  deleted: "Deleted",
};

const STATUS_STYLE: Record<Family["status"], string> = {
  active: "bg-[var(--forest-soft)] text-[var(--forest)]",
  deactivated: "bg-[var(--surface)] text-[var(--ink-soft)]",
  merged: "bg-[var(--gold-soft)] text-[var(--gold)]",
  deleted: "bg-[var(--clay-red-soft)] text-[var(--clay-red)]",
};

export default function FamilyRegistryPage() {
  const { includeInactive, toggleIncludeInactive, openDialog, activeDialog } = useFamilyUiStore();
  const { data: families, isLoading, isError, error } = useFamilies(includeInactive);
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    if (!families) return [];
    const q = query.trim().toLowerCase();
    if (!q) return families;
    return families.filter((f) => f.name.toLowerCase().includes(q));
  }, [families, query]);

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-6 py-6 sm:px-10">
        <div className="mx-auto max-w-6xl">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
                Family Register · {families?.length ?? 0} listed
              </p>
              <h1 className="font-display mt-1 text-4xl">Families</h1>
            </div>
            <button
              onClick={() => openDialog("add")}
              className="bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              Add family
            </button>
          </div>
          <p className="mt-2 max-w-xl text-sm text-[var(--ink-soft)]">
            Every family here belongs only to this community. Renaming, merging, or
            deactivating a family never affects any other community using Nsaabodeɛ Smart.
          </p>
        </div>
      </header>

      <div className="mx-auto flex max-w-6xl items-center gap-4 px-6 py-5 sm:px-10">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search families…"
          className="w-64 border-0 border-b-2 border-[var(--rule)] bg-transparent px-0 py-2 text-sm outline-none focus:border-[var(--forest)]"
        />
        <label className="flex items-center gap-2 text-sm text-[var(--ink-soft)]">
          <input type="checkbox" checked={includeInactive} onChange={toggleIncludeInactive} />
          Show deactivated, merged &amp; deleted
        </label>
      </div>

      <main className="mx-auto max-w-6xl px-6 pb-16 sm:px-10">
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading families…</p>}
        {isError && (
          <p className="text-sm text-[var(--clay-red)]">
            Couldn&apos;t load families: {error instanceof Error ? error.message : "unknown error"}
          </p>
        )}

        {!isLoading && !isError && filtered.length === 0 && (
          <div className="border border-dashed border-[var(--rule)] px-6 py-10 text-center">
            <p className="font-display text-lg">No families yet</p>
            <p className="mt-1 text-sm text-[var(--ink-soft)]">
              Add your first family to start assigning members and contribution rules.
            </p>
          </div>
        )}

        <ul className="divide-y divide-[var(--rule)] border-y-2 border-[var(--ink)]">
          {filtered.map((family, i) => (
            <li key={family.id} className="flex items-center gap-4 py-4">
              <span className="w-8 shrink-0 font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(3, "0")}</span>
              <span
                aria-hidden
                className="h-8 w-1.5 shrink-0 rounded-full"
                style={{ backgroundColor: crestColorFor(family.id) }}
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-3">
                  <h2 className="font-display truncate text-lg">{family.name}</h2>
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[family.status]}`}
                  >
                    {STATUS_LABEL[family.status]}
                  </span>
                  {family.family_head && (
                    <span className="rounded-full bg-[var(--gold-soft)] px-2 py-0.5 text-xs font-medium text-[var(--gold)]">
                      Head: {family.family_head.full_name}
                    </span>
                  )}
                </div>
                <p className="font-mono mt-0.5 text-xs text-[var(--ink-soft)]">
                  {family.member_count} active member{family.member_count === 1 ? "" : "s"}
                  {family.merged_into && " · merged into another family"}
                  {family.status === "active" && (
                    <>
                      {" · own-family rate: "}
                      {family.standing_family_rate ? formatCedis(family.standing_family_rate) : "not set"}
                      {family.recommended_family_rate && " (pending approval)"}
                    </>
                  )}
                </p>
              </div>

              <div className="flex shrink-0 flex-wrap gap-2 text-xs">
                {family.status === "active" && (
                  <>
                    <ActionButton onClick={() => openDialog("rate", family)}>Rate</ActionButton>
                    <ActionButton onClick={() => openDialog("rename", family)}>Rename</ActionButton>
                    <ActionButton onClick={() => openDialog("merge", family)}>Merge</ActionButton>
                    <ActionButton onClick={() => openDialog("transfer", family)}>
                      Transfer members
                    </ActionButton>
                    <ActionButton onClick={() => openDialog("deactivate", family)}>
                      Deactivate
                    </ActionButton>
                    <ActionButton tone="danger" onClick={() => openDialog("delete", family)}>
                      Delete
                    </ActionButton>
                  </>
                )}
                <ActionButton onClick={() => openDialog("history", family)}>History</ActionButton>
              </div>
            </li>
          ))}
        </ul>
      </main>

      {activeDialog === "add" && <AddFamilyDialog />}
      {activeDialog === "rename" && <RenameFamilyDialog />}
      {activeDialog === "merge" && <MergeFamilyDialog allFamilies={families ?? []} />}
      {activeDialog === "deactivate" && <DeactivateFamilyDialog />}
      {activeDialog === "delete" && <DeleteFamilyDialog />}
      {activeDialog === "transfer" && <TransferMembersDialog />}
      {activeDialog === "history" && <FamilyHistoryDrawer />}
      {activeDialog === "rate" && <FamilyRateDialog />}
    </div>
  );
}

function ActionButton({
  children,
  onClick,
  tone = "default",
}: {
  children: React.ReactNode;
  onClick: () => void;
  tone?: "default" | "danger";
}) {
  return (
    <button
      onClick={onClick}
      className={`border px-3 py-1.5 font-medium transition-colors ${
        tone === "danger"
          ? "border-[var(--clay-red)] text-[var(--clay-red)] hover:bg-[var(--clay-red-soft)]"
          : "border-[var(--rule)] text-[var(--ink)] hover:border-[var(--forest)] hover:text-[var(--forest)]"
      }`}
    >
      {children}
    </button>
  );
}
