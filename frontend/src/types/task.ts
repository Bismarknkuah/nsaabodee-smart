export type TaskStatus = "pending" | "in_progress" | "pending_approval" | "done";
export type TaskPriority = "low" | "medium" | "high" | "urgent";

export interface MemberTask {
  id: string;
  assigned_to: string;
  assigned_to_name: string;
  assigned_by_name: string | null;
  family: string | null;
  funeral_event: string | null;
  funeral_deceased_name: string | null;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  due_date: string | null;
  attachment: string | null;
  is_archived: boolean;
  approved_by_username: string | null;
  approved_at: string | null;
  rejection_note: string;
  created_at: string;
  updated_at: string;
}
