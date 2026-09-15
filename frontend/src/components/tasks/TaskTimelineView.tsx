"use client";

import type { MemberTask } from "@/types/task";

const STATUS_ACCENT: Record<string, string> = {
  pending: "var(--gold)", in_progress: "var(--violet)", pending_approval: "var(--clay-red)", done: "var(--forest)",
};

function groupLabel(dateStr: string | null): string {
  if (!dateStr) return "No due date";
  const date = new Date(dateStr);
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const diffDays = Math.round((date.getTime() - today.getTime()) / 86400000);
  if (diffDays < 0) return "Overdue";
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Tomorrow";
  if (diffDays <= 7) return "This week";
  return date.toLocaleDateString(undefined, { month: "long", year: "numeric" });
}

/** A real chronological view — grouped by when things are due, oldest/most-urgent first, not just a re-sorted list. */
export function TaskTimelineView({ tasks }: { tasks: MemberTask[] }) {
  const sorted = [...tasks].sort((a, b) => {
    if (!a.due_date && !b.due_date) return 0;
    if (!a.due_date) return 1;
    if (!b.due_date) return -1;
    return a.due_date.localeCompare(b.due_date);
  });

  const groups: { label: string; tasks: MemberTask[] }[] = [];
  for (const t of sorted) {
    const label = groupLabel(t.due_date);
    const existing = groups.find((g) => g.label === label);
    if (existing) existing.tasks.push(t);
    else groups.push({ label, tasks: [t] });
  }

  return (
    <div className="relative border-l-2 border-[var(--ink)] pl-6">
      {groups.map((group) => (
        <div key={group.label} className="relative mb-6">
          <div className="absolute -left-[1.95rem] top-1 h-3 w-3 rounded-full border-2 border-[var(--ink)] bg-[var(--paper)]" />
          <p className={`font-mono text-xs font-medium uppercase tracking-wide ${group.label === "Overdue" ? "text-[var(--clay-red)]" : "text-[var(--ink-soft)]"}`}>
            {group.label}
          </p>
          <ul className="mt-2 space-y-2">
            {group.tasks.map((t) => (
              <li key={t.id} className="flex items-center gap-3 rounded-sm border border-[var(--rule)] bg-white p-2 text-sm">
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: STATUS_ACCENT[t.status] }} />
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{t.title}</p>
                  <p className="text-xs text-[var(--ink-soft)]">
                    {t.assigned_to_name} · {t.priority}
                    {t.due_date && ` · ${new Date(t.due_date).toLocaleDateString()}`}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      ))}
      {groups.length === 0 && <p className="text-sm text-[var(--ink-soft)]">Nothing to show.</p>}
    </div>
  );
}
