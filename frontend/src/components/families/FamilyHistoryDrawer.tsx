"use client";

import { useFamilyAuditLog } from "@/lib/hooks/useFamilies";
import { useFamilyUiStore } from "@/store/familyUiStore";
import { DialogShell } from "./DialogShell";
import type { FamilyAuditAction } from "@/types/family";

const ACTION_LABEL: Record<FamilyAuditAction, string> = {
  created: "Family created",
  renamed: "Renamed",
  merged: "Merged into another family",
  deactivated: "Deactivated",
  reactivated: "Reactivated",
  deleted: "Deleted",
  head_assigned: "Family head assigned",
  member_transferred_in: "Member transferred in",
  member_transferred_out: "Member transferred out",
};

export function FamilyHistoryDrawer() {
  const { activeFamily } = useFamilyUiStore();
  const { data: logs, isLoading } = useFamilyAuditLog(activeFamily?.id ?? null);

  if (!activeFamily) return null;

  return (
    <DialogShell title={`History — ${activeFamily.name}`}>
      {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading history…</p>}
      {!isLoading && logs?.length === 0 && (
        <p className="text-sm text-[var(--ink-soft)]">No recorded changes yet.</p>
      )}
      <ul className="max-h-80 space-y-3 overflow-y-auto">
        {logs?.map((log) => (
          <li key={log.id} className="border-l-2 border-[var(--rule)] pl-3">
            <p className="text-sm font-medium">{ACTION_LABEL[log.action]}</p>
            <p className="font-mono text-xs text-[var(--ink-soft)]">
              {new Date(log.created_at).toLocaleString()} · {log.actor_name || "System"}
            </p>
          </li>
        ))}
      </ul>
    </DialogShell>
  );
}
