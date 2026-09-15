"use client";

import { useFamilyActions } from "@/lib/hooks/useFamilies";
import { useFamilyUiStore } from "@/store/familyUiStore";
import { DialogShell } from "./DialogShell";

export function DeactivateFamilyDialog() {
  const { activeFamily, closeDialog } = useFamilyUiStore();
  const { deactivate } = useFamilyActions();

  if (!activeFamily) return null;

  return (
    <DialogShell
      title={`Deactivate "${activeFamily.name}"`}
      description="Members stay assigned to this family and its history is kept. It just stops appearing as an option for new members, funerals, and contribution rules until reactivated."
    >
      {deactivate.isError && (
        <p className="mb-3 text-sm text-[var(--clay-red)]">
          {deactivate.error instanceof Error ? deactivate.error.message : "Couldn't deactivate family."}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <button onClick={closeDialog} className="px-3 py-2 text-sm text-[var(--ink-soft)]">
          Cancel
        </button>
        <button
          onClick={() => deactivate.mutate(activeFamily.id, { onSuccess: closeDialog })}
          disabled={deactivate.isPending}
          className="rounded-sm bg-[var(--ink)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {deactivate.isPending ? "Deactivating…" : "Deactivate"}
        </button>
      </div>
    </DialogShell>
  );
}
