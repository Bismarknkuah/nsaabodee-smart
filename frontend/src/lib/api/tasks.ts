import type { MemberTask, TaskPriority, TaskStatus } from "@/types/task";
import { authFetch } from "./authFetch";
import { unwrapPaginated } from "./unwrapPaginated";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authFetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail?.toString() ?? Object.values(body).flat().join(" ") ?? `Request failed (${res.status})`);
  }
  const json = await res.json();
  return unwrapPaginated<T>(json) as T;
}

export const tasksApi = {
  list: (includeArchived = false) => request<MemberTask[]>(`/tasks/${includeArchived ? "?include_archived=true" : ""}`),
  assign: (input: { assigned_to_id: string; title: string; description?: string; priority?: TaskPriority; due_date?: string; funeral_event_id?: string }) =>
    request<MemberTask>(`/tasks/`, { method: "POST", body: JSON.stringify(input) }),
  updateStatus: (id: string, status: TaskStatus) =>
    request<MemberTask>(`/tasks/${id}/`, { method: "PATCH", body: JSON.stringify({ status }) }),

  /** "Completion approval" — an assignee submits (status: "pending_approval"), the assigner decides here. */
  decideCompletion: (id: string, approved: boolean, rejectionNote?: string) =>
    request<MemberTask>(`/tasks/${id}/decide_completion/`, { method: "POST", body: JSON.stringify({ approved, rejection_note: rejectionNote }) }),
  reassign: (id: string, newAssigneeId: string) =>
    request<MemberTask>(`/tasks/${id}/reassign/`, { method: "POST", body: JSON.stringify({ new_assignee_id: newAssigneeId }) }),
  archive: (id: string) => request<MemberTask>(`/tasks/${id}/archive/`, { method: "POST" }),
  unarchive: (id: string) => request<MemberTask>(`/tasks/${id}/unarchive/`, { method: "POST" }),
};
