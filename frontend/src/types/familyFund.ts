export type FundPaymentMethod = "cash" | "mobile_money" | "bank" | "other";

export interface FamilyFund {
  id: string;
  family: string;
  name: string;
  description: string;
  is_active: boolean;
  created_at: string;
}

export interface FamilyFundContribution {
  id: string;
  fund: string;
  member: string;
  member_name: string;
  amount: string;
  payment_method: FundPaymentMethod;
  receipt_number: string;
  paid_at: string;
}

export interface FamilyFundSummary {
  fund_id: string;
  fund_name: string;
  is_active: boolean;
  contribution_count: number;
  contributor_count: number;
  total_collected: string;
}

export type ExpenseStatus = "pending" | "approved" | "rejected";

export interface FamilyFuneralExpense {
  id: string;
  family: string;
  funeral_event: string;
  funeral_deceased_name: string;
  item_name: string;
  seller_name: string;
  seller_contact: string;
  amount: string;
  date_purchased: string;
  paid_by_member: string | null;
  paid_by_member_name: string | null;
  status: ExpenseStatus;
  recorded_by_name: string | null;
  approved_by_name: string | null;
  approved_at: string | null;
  rejection_reason: string;
  created_at: string;
}

export interface ExpenditureBucket {
  count: number;
  total: string;
}

export interface FuneralExpenditureSummary {
  family_id: string;
  pending: ExpenditureBucket;
  approved: ExpenditureBucket;
  rejected: ExpenditureBucket;
  total_all_recorded: string;
}
