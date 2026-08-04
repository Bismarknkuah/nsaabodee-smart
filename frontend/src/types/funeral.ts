export type FuneralStatus = "pending_approval" | "active" | "closed" | "cancelled";
export type Gender = "male" | "female";
export type RateType = "own_family" | "general";
export type PaymentStatus = "unpaid" | "partial" | "paid";
export type PaymentMethod = "cash" | "mobile_money" | "bank" | "other";

export interface FuneralEvent {
  id: string;
  deceased_name: string;
  deceased_gender: Gender;
  deceased_family: string;
  deceased_family_name: string;
  date_of_death: string;
  burial_date: string | null;
  funeral_date: string | null;
  collection_start_date: string;
  collection_end_date: string | null;
  status: FuneralStatus;
  own_family_amount: string;
  general_male_amount: string;
  general_female_amount: string;
  created_at: string;
  updated_at: string;
}

export interface RateBucketSummary {
  member_count: number;
  expected_total: string;
  collected_total: string;
  outstanding_total: string;
  fully_paid_count: number;
  partial_count: number;
  unpaid_count: number;
}

export interface FuneralSummary {
  funeral_id: string;
  deceased_name: string;
  deceased_family: string;
  own_family: RateBucketSummary;
  general: RateBucketSummary;
}

export interface ObligationMember {
  id: string;
  full_name: string;
  gender: Gender;
  family: string | null;
}

export interface ContributionObligation {
  id: string;
  funeral_event: string;
  member: ObligationMember;
  rate_type: RateType;
  expected_amount: string;
  amount_paid: string;
  balance: string;
  payment_status: PaymentStatus;
}

export interface ApprovalProgress {
  funeral_id: string;
  status: FuneralStatus;
  required_approvals: number;
  approvals: { approved_by: string; approved_at: string }[];
  approval_count: number;
  still_needed: number;
}

export type DeskType = "community" | "elders" | "guest" | "family";

export interface DeskAssignment {
  id: string;
  funeral_event: string;
  user: string;
  username: string;
  desk_type: DeskType;
  assigned_by_username: string | null;
  created_at: string;
}

/** "Every funeral creates a committee workspace... Custom positions allowed." Deliberately separate from DeskAssignment above — this is organizational recognition, never a payment-collecting authority. */
export interface FuneralCommitteePosition {
  id: string;
  funeral_event: string;
  deceased_name: string;
  member: string;
  member_name: string;
  title: string;
  appointed_by_username: string | null;
  appointed_at: string;
}

export const SUGGESTED_FUNERAL_COMMITTEE_TITLES = [
  "Chairman", "Vice Chairman", "Secretary", "Treasurer", "Welfare Officer",
  "Logistics Officer", "Food Coordinator", "Transport Coordinator",
  "Accommodation Coordinator", "Protocol Officer", "Security Officer", "PR Officer",
];
