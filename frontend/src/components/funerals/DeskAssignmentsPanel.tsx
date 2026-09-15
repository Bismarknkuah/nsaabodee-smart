"use client";

import { useState } from "react";
import { useDeskAssignments, useAssignDeskWorker, useRemoveDeskAssignment } from "@/lib/hooks/useFunerals";
import { useAuthStore } from "@/store/authStore";
import type { DeskType } from "@/types/funeral";

const DESK_TYPE_LABEL: Record<DeskType, string> = {
  community: "Community Ledger",
  elders: "Town Elders",
  guest: "Guest",
  family: "Family",
};

/**
 * "Only the community treasurer, community admin and the family
 * treasurer are only allow to create or remove collector or assigned
 * collector." Chairman/Secretary and Family Head no longer open a
 * desk directly here — they approve instead, from their own pending
 * queue (see the Desk Assignment Approvals section on their
 * dashboard), not from this panel. Capability-based on the backend —
 * the assigned person's normal platform role doesn't matter; the
 * approved assignment alone is what lets them record real payments/
 * gifts for this one funeral.
 */
export function DeskAssignmentsPanel({ funeralId }: { funeralId: string }) {
  const user = useAuthStore((s) => s.user);
  const isCommunityAdmin = Boolean(user?.is_superuser || user?.role === "community_admin");
  const isCommunityTreasurer = user?.role === "treasurer";
  const isFamilyTreasurer = user?.role === "family_treasurer";
  const canInitiate = isCommunityAdmin || isCommunityTreasurer || isFamilyTreasurer;

  const availableTypes: DeskType[] = isCommunityAdmin
    ? ["community", "elders", "guest", "family"]
    : isCommunityTreasurer
    ? ["community", "elders", "guest"]
    : ["family"];

  const { data: assignments, isError } = useDeskAssignments(funeralId);
  const assign = useAssignDeskWorker(funeralId);
  const remove = useRemoveDeskAssignment(funeralId);

  const [expanded, setExpanded] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [deskType, setDeskType] = useState<DeskType>(availableTypes[0]);

  if (isError) return null; // not permitted to manage this funeral's desk — say nothing rather than show a broken panel

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) return;
    assign.mutate(
      { new_username: username.trim(), new_password: password, desk_type: deskType },
      { onSuccess: () => { setUsername(""); setPassword(""); } }
    );
  };

  if (!canInitiate) {
    // Viewing who's already assigned is fine for anyone who can see this funeral —
    // opening/removing an assignment is what's restricted to Treasurer/Admin.
    if (!assignments || assignments.length === 0) return null;
    return (
      <div className="mt-3 rounded-sm bg-[var(--surface)] p-3">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Desk assignments</p>
        <ul className="mt-2 space-y-1.5">
          {assignments.map((a) => (
            <li key={a.id} className="text-sm">
              {a.username} <span className="text-xs text-[var(--ink-soft)]">— {DESK_TYPE_LABEL[a.desk_type]} desk{!a.is_active && " · pending approval"}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  if (!expanded) {
    return (
      <button onClick={() => setExpanded(true)} className="mt-3 text-xs text-[var(--forest)] hover:underline">
        Assign someone to the funeral desk{assignments && assignments.length > 0 ? ` (${assignments.length} assigned)` : ""}
      </button>
    );
  }

  return (
    <div className="mt-3 rounded-sm bg-[var(--surface)] p-3">
      <p className="text-xs text-[var(--ink-soft)]">
        Whoever you assign here gets real permission to collect at that desk for THIS funeral
        only, once approved — a Family desk needs both the Family Secretary and Family Head to
        approve; a Community/Elders/Guest desk needs both the Chairman and Secretary. Opening
        it directly as Community Admin skips that wait — that authority already is the approval.
      </p>

      {assignments && assignments.length > 0 && (
        <ul className="mt-2 space-y-1.5">
          {assignments.map((a) => (
            <li key={a.id} className="flex items-center justify-between gap-2 text-sm">
              <span>
                {a.username} <span className="text-xs text-[var(--ink-soft)]">— {DESK_TYPE_LABEL[a.desk_type]} desk{!a.is_active && " · pending approval"}</span>
              </span>
              <button
                onClick={() => remove.mutate(a.id)}
                disabled={remove.isPending}
                className="text-xs text-[var(--clay-red)] hover:underline"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <form onSubmit={submit} className="mt-3 space-y-2 border-t border-[var(--rule)] pt-3">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Add a new desk worker</p>
        <div className="grid grid-cols-2 gap-2">
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Username for them to log in with"
            className="rounded-sm border border-[var(--rule)] bg-white px-2 py-1.5 text-xs outline-none focus:border-[var(--forest)]"
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Password (8+ characters)"
            className="rounded-sm border border-[var(--rule)] bg-white px-2 py-1.5 text-xs outline-none focus:border-[var(--forest)]"
          />
        </div>
        <select
          value={deskType}
          onChange={(e) => setDeskType(e.target.value as DeskType)}
          className="w-full rounded-sm border border-[var(--rule)] bg-white px-2 py-1.5 text-xs outline-none focus:border-[var(--forest)]"
        >
          {availableTypes.map((t) => (
            <option key={t} value={t}>{DESK_TYPE_LABEL[t]} desk</option>
          ))}
        </select>
        {assign.isError && <p className="text-xs text-[var(--clay-red)]">{(assign.error as Error).message}</p>}
        <div className="flex gap-2">
          <button
            type="submit"
            disabled={assign.isPending}
            className="rounded-sm bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
          >
            {assign.isPending ? "Assigning…" : "Assign"}
          </button>
          <button type="button" onClick={() => setExpanded(false)} className="text-xs text-[var(--ink-soft)]">
            Close
          </button>
        </div>
      </form>
    </div>
  );
}
