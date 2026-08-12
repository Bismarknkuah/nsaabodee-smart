"use client";

import { useState } from "react";
import type { Family } from "@/types/family";
import { useFamilyActions } from "@/lib/hooks/useFamilies";
import { useFamilyUiStore } from "@/store/familyUiStore";
import { DialogShell } from "./DialogShell";

export function MergeFamilyDialog({ allFamilies }: { allFamilies: Family[] }) {
  const { activeFamily, closeDialog } = useFamilyUiStore();
  const { merge } = useFamilyActions();
  const [targetId, setTargetId] = useState("");
  const [confirmed, setConfirmed] = useState(false);

  if (!activeFamily) return null;

  const candidates = allFamilies.filter(
    (f) => f.id !== activeFamily.id && f.status === "active"
  );
  const target = candidates.find((f) => f.id === targetId);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!target || !confirmed) return;
    merge.mutate({ sourceId: activeFamily.id, targetId: target.id }, { onSuccess: closeDialog });
  };

  return (
    <DialogShell
      title={`Merge "${activeFamily.name}"`}
      description="All active members move into the family you choose below. The old family is kept as history — it is never deleted — but becomes inactive."
    >
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="text-sm font-medium">Merge into</label>
          <select
            value={targetId}
            onChange={(e) => {
              setTargetId(e.target.value);
              setConfirmed(false);
            }}
            className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
          >
            <option value="">Choose a family…</option>
            {candidates.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name} ({f.member_count} members)
              </option>
            ))}
          </select>
        </div>

        {target && (
          <label className="flex items-start gap-2 text-sm text-[var(--ink-soft)]">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
              className="mt-0.5"
            />
            I understand all {activeFamily.member_count} member(s) of &quot;{activeFamily.name}&quot;
            will move to &quot;{target.name}&quot;, and this cannot be automatically undone.
          </label>
        )}

        {merge.isError && (
          <p className="text-sm text-[var(--clay-red)]">
            {merge.error instanceof Error ? merge.error.message : "Couldn't merge families."}
          </p>
        )}

        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={closeDialog} className="px-3 py-2 text-sm text-[var(--ink-soft)]">
            Cancel
          </button>
          <button
            type="submit"
            disabled={!target || !confirmed || merge.isPending}
            className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {merge.isPending ? "Merging…" : "Merge families"}
          </button>
        </div>
      </form>
    </DialogShell>
  );
}
