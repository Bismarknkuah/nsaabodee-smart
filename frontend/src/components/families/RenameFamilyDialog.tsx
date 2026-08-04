"use client";

import { useState } from "react";
import { useFamilyActions } from "@/lib/hooks/useFamilies";
import { useFamilyUiStore } from "@/store/familyUiStore";
import { DialogShell } from "./DialogShell";

export function RenameFamilyDialog() {
  const { activeFamily, closeDialog } = useFamilyUiStore();
  const { rename } = useFamilyActions();
  const [name, setName] = useState(activeFamily?.name ?? "");

  if (!activeFamily) return null;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim() || name.trim() === activeFamily.name) return;
    rename.mutate({ id: activeFamily.id, name: name.trim() }, { onSuccess: closeDialog });
  };

  return (
    <DialogShell
      title={`Rename "${activeFamily.name}"`}
      description="Existing members, contribution history, and funerals stay linked to this family under its new name."
    >
      <form onSubmit={submit} className="space-y-4">
        <input
          autoFocus
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
        />
        {rename.isError && (
          <p className="text-sm text-[var(--clay-red)]">
            {rename.error instanceof Error ? rename.error.message : "Couldn't rename family."}
          </p>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={closeDialog} className="px-3 py-2 text-sm text-[var(--ink-soft)]">
            Cancel
          </button>
          <button
            type="submit"
            disabled={rename.isPending}
            className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {rename.isPending ? "Saving…" : "Save name"}
          </button>
        </div>
      </form>
    </DialogShell>
  );
}
