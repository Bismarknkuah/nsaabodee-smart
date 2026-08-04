import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { tasksApi } from "@/lib/api/tasks";
import type { TaskStatus } from "@/types/task";

export function useTasks(includeArchived = false) {
  return useQuery({ queryKey: ["tasks", includeArchived], queryFn: () => tasksApi.list(includeArchived) });
}

export function useAssignTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: tasksApi.assign,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });
}

export function useUpdateTaskStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: TaskStatus }) => tasksApi.updateStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });
}

/** "Completion approval." */
export function useDecideTaskCompletion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, approved, rejectionNote }: { id: string; approved: boolean; rejectionNote?: string }) =>
      tasksApi.decideCompletion(id, approved, rejectionNote),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });
}

/** "Reassignment." */
export function useReassignTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, newAssigneeId }: { id: string; newAssigneeId: string }) => tasksApi.reassign(id, newAssigneeId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });
}

/** "Archive." */
export function useArchiveTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => tasksApi.archive(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });
}

export function useUnarchiveTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => tasksApi.unarchive(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["tasks"] }),
  });
}
