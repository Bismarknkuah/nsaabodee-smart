"use client";

import { useState } from "react";
import { useUpdateTaskStatus, useDecideTaskCompletion } from "@/lib/hooks/useTasks";
import type { MemberTask, TaskStatus } from "@/types/task";

const COLUMNS: { status: TaskStatus; label: string; accent: string }[] = [
  { status: "pending", label: "Pending", accent: "var(--gold)" },
  { status: "in_progress", label: "In Progress", accent: "var(--violet)" },
  { status: "pending_approval", label: "Pending Approval", accent: "var(--clay-red)" },
  { status: "done", label: "Done", accent: "var(--forest)" },
];

const PRIORITY_ACCENT: Record<string, string> = { low: "var(--ink-soft)", medium: "var(--gold)", high: "var(--clay-red)", urgent: "var(--clay-red)" };

/**
 * A real Kanban board — native HTML5 drag-and-drop between columns
 * (no library needed), not just a reskinned list. Dropping into
 * "Done" goes through the same completion-approval endpoint as
 * everywhere else, since a card being dragged doesn't bypass who's
 * actually allowed to approve a task's completion.
 */
export function TaskKanbanView({ tasks, canApprove }: { tasks: MemberTask[]; canApprove: boolean }) {
  const updateStatus = useUpdateTaskStatus();
  const decideCompletion = useDecideTaskCompletion();
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [overColumn, setOverColumn] = useState<TaskStatus | null>(null);

  const handleDrop = (task: MemberTask, targetStatus: TaskStatus) => {
    setOverColumn(null);
    setDraggingId(null);
    if (task.status === targetStatus) return;
    if (targetStatus === "done") {
      if (task.status !== "pending_approval") return; // must go through Pending Approval first
      if (canApprove) decideCompletion.mutate({ id: task.id, approved: true });
      return;
    }
    updateStatus.mutate({ id: task.id, status: targetStatus });
  };

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {COLUMNS.map((col) => {
        const columnTasks = tasks.filter((t) => t.status === col.status);
        return (
          <div
            key={col.status}
            onDragOver={(e) => { e.preventDefault(); setOverColumn(col.status); }}
            onDragLeave={() => setOverColumn(null)}
            onDrop={(e) => {
              e.preventDefault();
              const task = tasks.find((t) => t.id === draggingId);
              if (task) handleDrop(task, col.status);
            }}
            className="min-h-[16rem] rounded-sm border border-[var(--rule)] bg-[var(--surface)] p-3"
            style={{ outline: overColumn === col.status ? `2px dashed ${col.accent}` : "none" }}
          >
            <p className="font-mono text-[10px] font-medium uppercase tracking-wide" style={{ color: col.accent }}>
              {col.label} — {columnTasks.length}
            </p>
            <div className="mt-2 space-y-2">
              {columnTasks.map((t) => (
                <div
                  key={t.id}
                  draggable
                  onDragStart={() => setDraggingId(t.id)}
                  onDragEnd={() => setDraggingId(null)}
                  className="cursor-grab rounded-sm border border-[var(--rule)] bg-white p-2 text-sm active:cursor-grabbing"
                  style={{ opacity: draggingId === t.id ? 0.5 : 1 }}
                >
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium">{t.title}</p>
                    <span className="shrink-0 font-mono text-[9px] uppercase" style={{ color: PRIORITY_ACCENT[t.priority] }}>{t.priority}</span>
                  </div>
                  <p className="mt-1 text-xs text-[var(--ink-soft)]">
                    {t.assigned_to_name}{t.due_date && ` · due ${new Date(t.due_date).toLocaleDateString()}`}
                  </p>
                  {t.rejection_note && col.status === "in_progress" && (
                    <p className="mt-1 text-xs text-[var(--clay-red)]">↩ {t.rejection_note}</p>
                  )}
                </div>
              ))}
              {columnTasks.length === 0 && <p className="text-xs text-[var(--ink-soft)]">Nothing here.</p>}
            </div>
          </div>
        );
      })}
    </div>
  );
}
