"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { membersApi } from "@/lib/api/members";
import { useFamilyActions } from "@/lib/hooks/useFamilies";
import { useFamilyUiStore } from "@/store/familyUiStore";
import { DialogShell } from "./DialogShell";

export function TransferMembersDialog() {
  const { activeFamily, closeDialog } = useFamilyUiStore();
  const { transferMembers } = useFamilyActions();
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const { data: results, isFetching } = useQuery({
    queryKey: ["member-search", query],
    queryFn: () => membersApi.list({ search: query }),
    enabled: query.trim().length >= 2,
  });

  if (!activeFamily) return null;

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const submit = () => {
    if (selected.size === 0) return;
    transferMembers.mutate(
      { targetId: activeFamily.id, memberIds: Array.from(selected) },
      { onSuccess: closeDialog }
    );
  };

  return (
    <DialogShell
      title={`Transfer members into "${activeFamily.name}"`}
      description="Search for members from any family in this community and move them here."
    >
      <input
        autoFocus
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search by name…"
        className="w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
      />

      <div className="mt-3 max-h-56 overflow-y-auto rounded-sm border border-[var(--rule)]">
        {isFetching && <p className="p-3 text-sm text-[var(--ink-soft)]">Searching…</p>}
        {!isFetching && query.trim().length >= 2 && results?.length === 0 && (
          <p className="p-3 text-sm text-[var(--ink-soft)]">No members found.</p>
        )}
        {results?.map((m) => (
          <label
            key={m.id}
            className="flex cursor-pointer items-center gap-2 border-b border-[var(--rule)] px-3 py-2 text-sm last:border-b-0 hover:bg-[var(--paper)]"
          >
            <input type="checkbox" checked={selected.has(m.id)} onChange={() => toggle(m.id)} />
            {m.full_name}
          </label>
        ))}
      </div>

      <p className="mt-2 font-mono text-xs text-[var(--ink-soft)]">
        {selected.size} member{selected.size === 1 ? "" : "s"} selected
      </p>

      {transferMembers.isError && (
        <p className="mt-2 text-sm text-[var(--clay-red)]">
          {transferMembers.error instanceof Error
            ? transferMembers.error.message
            : "Couldn't transfer members."}
        </p>
      )}

      <div className="mt-4 flex justify-end gap-2">
        <button onClick={closeDialog} className="px-3 py-2 text-sm text-[var(--ink-soft)]">
          Cancel
        </button>
        <button
          onClick={submit}
          disabled={selected.size === 0 || transferMembers.isPending}
          className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {transferMembers.isPending ? "Transferring…" : "Transfer selected"}
        </button>
      </div>
    </DialogShell>
  );
}
