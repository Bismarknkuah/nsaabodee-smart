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

const COMMUNITY_WIDE_ROLES = ["community_admin", "chairman", "secretary"];

/**
 * "The community chairman or secretary can open two or more community
 * ledger payment desks... a separate desk for the community elders...
 * one or more guest payment desks... the abusuapanin/head and secretary
 * of the deceased family can also create family desks." Capability
 * -based on the backend — the assigned person's normal platform role
 * doesn't matter; this assignment alone is what lets them record real
 * payments/gifts for this one funeral. Which desk PURPOSES you're
 * allowed to open depends on who you are: Chairman/Secretary/Admin can
 * open any of the four; a Family Head/Secretary can only open a Family
 * desk, and only for their own family's funeral (the backend enforces
 * this regardless — this just avoids offering an option that would
 * only bounce back as an error).
 */
export function DeskAssignmentsPanel({ funeralId }: { funeralId: string }) {
  const user = useAuthStore((s) => s.user);
  const isCommunityWide = Boolean(user?.is_superuser || (user?.role && COMMUNITY_WIDE_ROLES.includes(user.role)));
  const availableTypes: DeskType[] = isCommunityWide ? ["community", "elders", "guest", "family"] : ["family"];

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
        only, whether or not they&apos;re a registered member or hold any other role.
      </p>

      {assignments && assignments.length > 0 && (
        <ul className="mt-2 space-y-1.5">
          {assignments.map((a) => (
            <li key={a.id} className="flex items-center justify-between gap-2 text-sm">
              <span>
                {a.username} <span className="text-xs text-[var(--ink-soft)]">— {DESK_TYPE_LABEL[a.desk_type]} desk</span>
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
