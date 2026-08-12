"use client";

import { useState } from "react";
import { useCreateBereavedRep } from "@/lib/hooks/useFamilies";
import { useFamilyUiStore } from "@/store/familyUiStore";
import { DialogShell } from "./DialogShell";

/**
 * 'Each funeral must have a bereaved rep, and the rep should represent
 * the family... that account should be created by the community
 * admin, secretary or chair but when one create she need other one to
 * approved.' Only requires a username and password here — an existing
 * member profile is optional, matching the same "a trusted family
 * friend, member or not" pattern already used for front desk
 * assignments.
 */
export function BereavedRepDialog() {
  const { activeFamily, closeDialog } = useFamilyUiStore();
  const createBereavedRep = useCreateBereavedRep(activeFamily?.id ?? "");

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const canSubmit = username.trim() && password.length >= 8;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    createBereavedRep.mutate(
      { new_username: username.trim(), new_password: password },
      { onSuccess: closeDialog }
    );
  };

  if (!activeFamily) return null;

  return (
    <DialogShell
      title={`Assign Bereaved Rep — ${activeFamily.name}`}
      description="Represents this whole family — every one of their active funerals shows on this account's own dashboard, not just one. Community Admin's own assignment is active right away; Secretary or Chairman's needs a different one of those three to approve before it works."
    >
      <form onSubmit={submit} className="space-y-4">
        <div>
          <label className="text-sm font-medium">Username</label>
          <input
            autoFocus value={username} onChange={(e) => setUsername(e.target.value)} placeholder="e.g. asona_bereaved_rep"
            className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
          />
        </div>
        <div>
          <label className="text-sm font-medium">Password</label>
          <input
            type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="8+ characters"
            className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
          />
        </div>

        {createBereavedRep.isError && (
          <p className="text-sm text-[var(--clay-red)]">
            {createBereavedRep.error instanceof Error ? createBereavedRep.error.message : "Couldn't create this account."}
          </p>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={closeDialog} className="px-3 py-2 text-sm text-[var(--ink-soft)]">
            Cancel
          </button>
          <button
            type="submit"
            disabled={createBereavedRep.isPending || !canSubmit}
            className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {createBereavedRep.isPending ? "Creating…" : "Create account"}
          </button>
        </div>
      </form>
    </DialogShell>
  );
}
