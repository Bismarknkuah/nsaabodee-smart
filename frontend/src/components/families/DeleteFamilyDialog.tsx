"use client";

import { useState } from "react";
import { useFamilyActions } from "@/lib/hooks/useFamilies";
import { useFamilyUiStore } from "@/store/familyUiStore";
import { DialogShell } from "./DialogShell";

export function DeleteFamilyDialog() {
  const { activeFamily, closeDialog } = useFamilyUiStore();
  const { remove } = useFamilyActions();
  const [force, setForce] = useState(false);

  if (!activeFamily) return null;

  const hasMembers = activeFamily.member_count > 0;

  return (
    <DialogShell
      title={`Delete "${activeFamily.name}"`}
      description="This soft-deletes the family. Contribution and funeral records that reference it are never removed."
    >
      {hasMembers && (
        <div className="mb-4 rounded-sm bg-[var(--clay-red-soft)] p-3 text-sm text-[var(--clay-red)]">
          This family still has {activeFamily.member_count} active member(s). Transfer or merge
          them out first, or check the box below to unassign them from any family and delete anyway.
        </div>
      )}

      {hasMembers && (
        <label className="mb-4 flex items-start gap-2 text-sm text-[var(--ink-soft)]">
          <input type="checkbox" checked={force} onChange={(e) => setForce(e.target.checked)} className="mt-0.5" />
          Unassign all {activeFamily.member_count} member(s) and delete this family anyway.
        </label>
      )}

      {remove.isError && (
        <p className="mb-3 text-sm text-[var(--clay-red)]">
          {remove.error instanceof Error ? remove.error.message : "Couldn't delete family."}
        </p>
      )}

      <div className="flex justify-end gap-2">
        <button onClick={closeDialog} className="px-3 py-2 text-sm text-[var(--ink-soft)]">
          Cancel
        </button>
        <button
          onClick={() => remove.mutate({ id: activeFamily.id, force }, { onSuccess: closeDialog })}
          disabled={(hasMembers && !force) || remove.isPending}
          className="rounded-sm bg-[var(--clay-red)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {remove.isPending ? "Deleting…" : "Delete family"}
        </button>
      </div>
    </DialogShell>
  );
}
