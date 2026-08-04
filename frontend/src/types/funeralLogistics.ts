export type ExpenseCategory =
  | "catering" | "transport" | "coffin" | "venue" | "printing" | "burial_fees" | "other";
export type ExpensePaymentMethod = "cash" | "mobile_money" | "bank" | "other";
export type ExpenseStatus = "pending_approval" | "paid" | "partial" | "credit" | "cancelled";

export interface FuneralExpense {
  id: string;
  funeral_event: string;
  description: string;
  category: ExpenseCategory;
  item_name: string;
  quantity: number | null;
  unit_price: string | null;
  amount: string;
  supplier_name: string;
  buyer: string | null;
  buyer_name: string | null;
  notes: string;
  invoice: string | null;
  payment_method: ExpensePaymentMethod;
  status: ExpenseStatus;
  amount_paid: string;
  balance_owed: string;
  voucher_number: string;
  incurred_on: string;
  recorded_by_username: string | null;
  approved_by_username: string | null;
  approved_at: string | null;
  created_at: string;
}

export interface ExpenseSummary {
  funeral_id: string;
  expense_count: number;
  cancelled_count: number;
  total_expenses: string;
  total_owed: string;
  by_category: Record<string, string>;
}

export interface FuneralAttendanceRecord {
  id: string;
  funeral_event: string;
  member: string | null;
  member_name: string | null;
  guest_name: string;
  display_name: string;
  attended_at: string;
}

export interface AttendanceSummary {
  funeral_id: string;
  members_attended: number;
  obligated_member_count: number;
  guests_attended: number;
  guest_names: string[];
}

export interface FinancialOverview {
  funeral_id: string;
  contributions_collected: string;
  gift_cash_collected: string;
  gift_estimated_item_value: string;
  total_expenses: string;
  net_cash_position: string;
}
