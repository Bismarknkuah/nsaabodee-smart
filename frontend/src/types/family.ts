export type FamilyStatus = "active" | "deactivated" | "merged" | "deleted";

export interface FamilyHead {
  id: string;
  full_name: string;
  gender: "male" | "female";
  status: string;
}

export interface Family {
  id: string;
  name: string;
  slug: string;
  description: string;
  status: FamilyStatus;
  family_head: FamilyHead | null;
  family_secretary: FamilyHead | null;
  family_treasurer: FamilyHead | null;
  member_count: number;
  merged_into: string | null;
  recommended_family_rate: string | null;
  standing_family_rate: string | null;
  created_at: string;
  updated_at: string;
  deactivated_at: string | null;
  deleted_at: string | null;
}

export type FamilyAuditAction =
  | "created"
  | "renamed"
  | "merged"
  | "deactivated"
  | "reactivated"
  | "deleted"
  | "head_assigned"
  | "member_transferred_in"
  | "member_transferred_out";

export interface FamilyAuditLogEntry {
  id: string;
  family: string;
  action: FamilyAuditAction;
  actor: string | null;
  actor_name: string;
  detail: Record<string, unknown>;
  created_at: string;
}
