"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTasks, useAssignTask, useUpdateTaskStatus, useDecideTaskCompletion, useReassignTask, useArchiveTask } from "@/lib/hooks/useTasks";
import { membersApi } from "@/lib/api/members";
import { useAuthStore } from "@/store/authStore";
import { KpiTile } from "@/components/dashboard/DashboardVisuals";
import { TaskKanbanView } from "@/components/tasks/TaskKanbanView";
import { TaskCalendarView } from "@/components/tasks/TaskCalendarView";
import { TaskTimelineView } from "@/components/tasks/TaskTimelineView";
import type { TaskPriority, TaskStatus } from "@/types/task";

const STATUS_LABEL: Record<TaskStatus, string> = {
  pending: "Pending", in_progress: "In Progress", pending_approval: "Pending Approval", done: "Done",
};
const STATUS_ACCENT: Record<TaskStatus, string> = {
  pending: "var(--gold)", in_progress: "var(--violet)", pending_approval: "var(--clay-red)", done: "var(--forest)",
};
const PRIORITY_ACCENT: Record<TaskPriority, string> = {
  low: "var(--ink-soft)", medium: "var(--gold)", high: "var(--clay-red)", urgent: "var(--clay-red)",
};

const CAN_ASSIGN_TASKS = ["community_admin", "chairman", "secretary", "family_head"];
type ViewMode = "list" | "kanban" | "calendar" | "timeline";

export default function TasksPage() {
  const user = useAuthStore((s) => s.user);
  const [includeArchived, setIncludeArchived] = useState(false);
  const { data: tasks, isLoading } = useTasks(includeArchived);
  const updateStatus = useUpdateTaskStatus();
  const decideCompletion = useDecideTaskCompletion();
  const reassign = useReassignTask();
  const archive = useArchiveTask();
  const [showAssign, setShowAssign] = useState(false);
  const [view, setView] = useState<ViewMode>("list");
  const [reassigningId, setReassigningId] = useState<string | null>(null);
  const [rejectingId, setRejectingId] = useState<string | null>(null);
  const [rejectionNote, setRejectionNote] = useState("");

  const pendingCount = tasks?.filter((t) => t.status !== "done").length ?? 0;
  const canAssign = !!user?.role && CAN_ASSIGN_TASKS.includes(user.role);
  // "Completion approval" — the same people who can assign a task are the people who can decide whether it's genuinely finished.
  const canApprove = canAssign;

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
          {user?.role === "family_head" ? "Your family" : "Community"}
        </p>
        <div className="mt-1 flex items-start justify-between gap-4">
          <div>
            <h1 className="font-display text-4xl">Tasks</h1>
            <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
              {canAssign
                ? "A Family Head can assign tasks to members of their own family; the Chairman or Secretary can assign to anyone in the community. Everyone can update the status of tasks assigned to them, but only an assigner decides whether finished work is actually approved."
                : "Tasks assigned to you by the Chairman, Secretary, Community Admin, or your Family Head. Submit your work for approval when it's done — an assigner reviews it from there."}
            </p>
          </div>
          {canAssign && (
            <button onClick={() => setShowAssign(true)} className="shrink-0 bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white">
              Assign a task
            </button>
          )}
        </div>
      </header>

      <main className="px-8 py-8">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="grid grid-cols-2 gap-px border border-[var(--rule)] bg-[var(--rule)] sm:max-w-md">
            <KpiTile label="Still open" value={pendingCount} color={pendingCount > 0 ? "gold" : "forest"} />
            <KpiTile label="Total" value={tasks?.length ?? 0} color="forest" />
          </div>

          <div className="flex items-center gap-3">
            {canAssign && (
              <label className="flex items-center gap-1.5 text-xs text-[var(--ink-soft)]">
                <input type="checkbox" checked={includeArchived} onChange={(e) => setIncludeArchived(e.target.checked)} />
                Show archived
              </label>
            )}
            <div className="flex rounded-sm border border-[var(--rule)]">
              {(["list", "kanban", "calendar", "timeline"] as ViewMode[]).map((v) => (
                <button
                  key={v}
                  onClick={() => setView(v)}
                  className={`px-3 py-1.5 text-xs font-medium capitalize ${view === v ? "bg-[var(--ink)] text-white" : "hover:bg-[var(--surface)]"}`}
                >
                  {v}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="mt-6">
          {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
          {tasks?.length === 0 && (
            <div className="border border-dashed border-[var(--rule)] px-6 py-10 text-center">
              <p className="font-display text-lg">No tasks yet</p>
            </div>
          )}

          {tasks && tasks.length > 0 && view === "kanban" && <TaskKanbanView tasks={tasks} canApprove={canApprove} />}
          {tasks && tasks.length > 0 && view === "calendar" && <TaskCalendarView tasks={tasks} />}
          {tasks && tasks.length > 0 && view === "timeline" && <TaskTimelineView tasks={tasks} />}

          {tasks && tasks.length > 0 && view === "list" && (
            <ol className="divide-y divide-[var(--rule)] border-y-2 border-[var(--ink)]">
              {tasks.map((t, i) => (
                <li key={t.id} className="flex items-start gap-3 py-4" style={{ borderLeft: `3px solid ${STATUS_ACCENT[t.status]}` }}>
                  <span className="pl-3 font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(3, "0")}</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium">{t.title}</p>
                      <span className="font-mono text-[10px] font-medium uppercase tracking-wide" style={{ color: STATUS_ACCENT[t.status] }}>
                        {STATUS_LABEL[t.status]}
                      </span>
                      <span className="font-mono text-[10px] uppercase" style={{ color: PRIORITY_ACCENT[t.priority] }}>{t.priority}</span>
                      {t.is_archived && <span className="text-[10px] text-[var(--ink-soft)]">archived</span>}
                    </div>
                    {t.description && <p className="mt-1 text-sm text-[var(--ink-soft)]">{t.description}</p>}
                    {t.attachment && (
                      <a href={t.attachment} target="_blank" rel="noreferrer" className="mt-1 inline-block text-xs text-[var(--forest)] hover:underline">
                        View attachment
                      </a>
                    )}
                    {t.rejection_note && (
                      <p className="mt-1 text-xs text-[var(--clay-red)]">Sent back: {t.rejection_note}</p>
                    )}
                    <p className="mt-1 text-xs text-[var(--ink-soft)]">
                      Assigned to {t.assigned_to_name}
                      {t.assigned_by_name && ` by ${t.assigned_by_name}`}
                      {t.funeral_deceased_name && ` · for ${t.funeral_deceased_name}'s funeral`}
                      {t.due_date && ` · due ${new Date(t.due_date).toLocaleDateString()}`}
                      {t.approved_by_username && ` · approved by ${t.approved_by_username}`}
                    </p>

                    {rejectingId === t.id && (
                      <div className="mt-2 flex gap-2">
                        <input
                          value={rejectionNote}
                          onChange={(e) => setRejectionNote(e.target.value)}
                          placeholder="What still needs work?"
                          className="flex-1 rounded-sm border border-[var(--rule)] px-2 py-1 text-xs"
                        />
                        <button
                          onClick={() => { if (rejectionNote.trim()) { decideCompletion.mutate({ id: t.id, approved: false, rejectionNote: rejectionNote.trim() }); setRejectingId(null); setRejectionNote(""); } }}
                          className="rounded-sm border border-[var(--clay-red)] px-2 py-1 text-xs text-[var(--clay-red)]"
                        >
                          Send back
                        </button>
                      </div>
                    )}
                    {reassigningId === t.id && (
                      <ReassignRow taskId={t.id} onDone={() => setReassigningId(null)} onReassign={reassign} />
                    )}
                  </div>

                  <div className="mr-3 flex shrink-0 flex-col items-end gap-1">
                    {t.status !== "done" && t.status !== "pending_approval" && (
                      <select
                        value={t.status}
                        onChange={(e) => updateStatus.mutate({ id: t.id, status: e.target.value as TaskStatus })}
                        className="border border-[var(--rule)] px-2 py-1 text-xs"
                      >
                        <option value="pending">Pending</option>
                        <option value="in_progress">In Progress</option>
                        <option value="pending_approval">Submit for approval</option>
                      </select>
                    )}
                    {t.status === "pending_approval" && canApprove && (
                      <div className="flex gap-1">
                        <button onClick={() => decideCompletion.mutate({ id: t.id, approved: true })} className="rounded-sm border border-[var(--forest)] px-2 py-1 text-xs text-[var(--forest)]">Approve</button>
                        <button onClick={() => setRejectingId(t.id)} className="rounded-sm border border-[var(--clay-red)] px-2 py-1 text-xs text-[var(--clay-red)]">Reject</button>
                      </div>
                    )}
                    {canAssign && t.status !== "done" && (
                      <div className="flex gap-2 text-[10px]">
                        <button onClick={() => setReassigningId(t.id === reassigningId ? null : t.id)} className="text-[var(--ink-soft)] hover:underline">Reassign</button>
                        {!t.is_archived && <button onClick={() => archive.mutate(t.id)} className="text-[var(--ink-soft)] hover:underline">Archive</button>}
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
        </div>
      </main>

      {showAssign && <AssignTaskDialog onClose={() => setShowAssign(false)} />}
    </div>
  );
}

function ReassignRow({ taskId, onDone, onReassign }: { taskId: string; onDone: () => void; onReassign: ReturnType<typeof useReassignTask> }) {
  const [query, setQuery] = useState("");
  const { data: memberResults } = useQuery({
    queryKey: ["task-reassign-search", query],
    queryFn: () => membersApi.list({ search: query }),
    enabled: query.trim().length >= 2,
  });

  return (
    <div className="mt-2">
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search a new assignee…"
        className="w-full max-w-xs rounded-sm border border-[var(--rule)] px-2 py-1 text-xs"
      />
      {memberResults && memberResults.length > 0 && (
        <ul className="mt-1 max-h-24 max-w-xs divide-y divide-[var(--rule)] overflow-y-auto rounded-sm border border-[var(--rule)] bg-white">
          {memberResults.map((m) => (
            <li key={m.id}>
              <button
                onClick={() => onReassign.mutate({ id: taskId, newAssigneeId: m.id }, { onSuccess: onDone })}
                className="block w-full px-2 py-1 text-left text-xs hover:bg-[var(--surface)]"
              >
                {m.full_name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// 'The available task he can assign should be available for selection
// instead of typing them.' A suggested, editable list — not a rigid
// enum — matching the same "suggestions, not requirements" pattern
// already used for committee/officer titles elsewhere in this
// platform. "Other" reveals a free-text field for anything not covered.
const SUGGESTED_TASK_TITLES = [
  "Arrange chairs and canopy", "Coordinate catering", "Arrange transport for guests",
  "Greet and usher guests", "Manage sound system", "Set up venue decorations",
  "Coordinate burial logistics", "Distribute programme/obituary", "Collect guest book signatures",
  "Clean up after the event", "Welcome guests at the gate", "Other (type your own)",
];

function AssignTaskDialog({ onClose }: { onClose: () => void }) {
  const assign = useAssignTask();
  const [query, setQuery] = useState("");
  const [assignedToId, setAssignedToId] = useState("");
  const [assignedToName, setAssignedToName] = useState("");
  const [title, setTitle] = useState("");
  const [titleSelection, setTitleSelection] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState<TaskPriority>("medium");
  const [dueDate, setDueDate] = useState("");

  const { data: memberResults } = useQuery({
    queryKey: ["task-assignee-search", query],
    queryFn: () => membersApi.list({ search: query }),
    enabled: query.trim().length >= 2 && !assignedToId,
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!assignedToId || !title.trim()) return;
    assign.mutate(
      { assigned_to_id: assignedToId, title: title.trim(), description: description || undefined, priority, due_date: dueDate || undefined },
      { onSuccess: onClose }
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="font-body w-full max-w-sm rounded-sm bg-[var(--surface)] p-6 text-[var(--ink)] shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <h2 className="font-display text-xl">Assign a task</h2>
          <button onClick={onClose} className="text-[var(--ink-soft)] hover:text-[var(--ink)]" aria-label="Close">✕</button>
        </div>

        <form onSubmit={submit} className="mt-4 space-y-4">
          <div>
            <label className="text-sm font-medium">Assign to</label>
            {assignedToId ? (
              <div className="mt-1 flex items-center justify-between rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm">
                <span>{assignedToName}</span>
                <button type="button" onClick={() => { setAssignedToId(""); setQuery(""); }} className="text-xs text-[var(--clay-red)]">
                  Change
                </button>
              </div>
            ) : (
              <>
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search a member…"
                  className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
                />
                {memberResults && memberResults.length > 0 && (
                  <ul className="mt-2 max-h-32 divide-y divide-[var(--rule)] overflow-y-auto rounded-sm bg-white">
                    {memberResults.map((m) => (
                      <li key={m.id}>
                        <button
                          type="button"
                          onClick={() => { setAssignedToId(m.id); setAssignedToName(m.full_name); }}
                          className="w-full px-3 py-2 text-left text-sm hover:bg-[var(--surface)]"
                        >
                          {m.full_name}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </div>

          <div>
            <label className="text-sm font-medium">Task</label>
            <select
              value={titleSelection}
              onChange={(e) => {
                setTitleSelection(e.target.value);
                if (e.target.value !== "Other (type your own)") setTitle(e.target.value);
                else setTitle("");
              }}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            >
              <option value="">Select a task…</option>
              {SUGGESTED_TASK_TITLES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            {titleSelection === "Other (type your own)" && (
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Describe the task"
                autoFocus
                className="mt-2 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
              />
            )}
          </div>
          <div>
            <label className="text-sm font-medium">Details (optional)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="text-sm font-medium">Priority</label>
              <select value={priority} onChange={(e) => setPriority(e.target.value as TaskPriority)}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm">
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>
            <div className="flex-1">
              <label className="text-sm font-medium">Due date</label>
              <input
                type="date"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
              />
            </div>
          </div>

          {assign.isError && <p className="text-sm text-[var(--clay-red)]">{assign.error.message}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-3 py-2 text-sm text-[var(--ink-soft)]">Cancel</button>
            <button
              type="submit"
              disabled={assign.isPending || !assignedToId || !title.trim()}
              className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {assign.isPending ? "Assigning…" : "Assign task"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
