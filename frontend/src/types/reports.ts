export interface MethodBreakdown {
  cash: string;
  mobile_money: string;
  bank: string;
  other: string;
}

export interface CollectionsReport {
  start_date: string;
  end_date: string;
  collector_id: string | null;
  contributions: { count: number; total: string; by_method: MethodBreakdown };
  /** Absent entirely for committee roles (Treasurer/Chairman/Secretary/Financial Secretary/Auditor) — see the backend's _includes_gift_cash_for. Present for Community Admin+ and a collector's own performance report. */
  gift_cash?: { count: number; total: string; by_method: MethodBreakdown };
  combined_cash_position_by_method: MethodBreakdown;
  receipts_issued: number;
  collector_name?: string;
}

export interface LedgerBucket {
  obligation_count: number;
  expected_total: string;
  collected_total: string;
}

export interface DonationLedgerBucket {
  donor_count: number;
  total_value: string;
}

export interface DonationReceiverEntry {
  member_id: string;
  member_name: string;
  donation_count: number;
  total_received: string;
}

export interface FamilyStatement {
  family_id: string;
  family_name: string;
  member_count: number;
  family_ledger: LedgerBucket;
  community_ledger: LedgerBucket;
  /** The four fields below are only present for this family's own head, Community Admin+, or a superuser — stripped entirely for the rest of the funeral committee, per "the funeral committee should have access to all the money paid except the donations." */
  guest_ledger?: DonationLedgerBucket;
  town_leaders_ledger?: DonationLedgerBucket;
  donation_receivers?: DonationReceiverEntry[];
  gifts_received?: { total_cash: string };
  // Kept for backward compatibility — same numbers as family_ledger.
  as_deceaseds_family: LedgerBucket;
  members_as_outsiders_elsewhere: LedgerBucket;
}

export interface FuneralLedgerBreakdown {
  funeral_id: string;
  deceased_name: string;
  deceased_family_name: string;
  family_ledger: { member_count: number; expected_total: string; collected_total: string };
  community_ledger: { member_count: number; expected_total: string; collected_total: string };
  guest_ledger?: DonationLedgerBucket;
  town_leaders_ledger?: DonationLedgerBucket;
}

export interface OutstandingMembersReport {
  community_id: string;
  outstanding_member_count: number;
  members: { member_id: string; member_name: string; total_owed: string; funeral_count: number }[];
}

export interface ExpenseStatement {
  start_date: string;
  end_date: string;
  expense_count: number;
  total: string;
  by_category: Record<string, string>;
}

export type DeliveryChannel = "physical" | "electronic";

export interface ReceiptEntry {
  ledger: "contribution" | "gift";
  receipt_number: string;
  delivery_channel: DeliveryChannel;
  amount?: string;
  total_value?: string;
  payment_method: string;
  funeral_deceased_name: string;
  date: string;
  time: string;
  member_name?: string;
  donor_name?: string;
  family_name?: string;
  recipient_family_name?: string;
  payment_id?: string;
  donation_id?: string;
}

export interface MyReceiptsResponse {
  has_member_profile: boolean;
  member_name?: string;
  receipts: ReceiptEntry[];
}

export interface OutstandingObligation {
  obligation_id: string;
  funeral_id: string;
  deceased_name: string;
  deceased_family_name: string;
  rate_type: "own_family" | "general";
  expected_amount: string;
  amount_paid: string;
  balance: string;
  payment_status: "unpaid" | "partial" | "paid";
}

export interface FuneralDailyBreakdownDay {
  date: string;
  contributions_total: string;
  contributions_count: number;
  gifts_total?: string;
  gifts_count?: number;
  combined_total: string;
}

export interface FuneralDailyBreakdown {
  funeral_id: string;
  collection_start_date: string;
  collection_end_date: string | null;
  status: string;
  days: FuneralDailyBreakdownDay[];
  grand_total: string;
}
