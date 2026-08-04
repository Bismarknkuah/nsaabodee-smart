import type {
  AttendanceSummary,
  ExpenseCategory,
  ExpensePaymentMethod,
  ExpenseStatus,
  ExpenseSummary,
  FinancialOverview,
  FuneralAttendanceRecord,
  FuneralExpense,
} from "@/types/funeralLogistics";
import { authFetch } from "./authFetch";
import { unwrapPaginated } from "./unwrapPaginated";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authFetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const message = body.detail?.toString() ?? Object.values(body).flat().join(" ") ?? `Request failed (${res.status})`;
    throw new Error(message);
  }
  const json = await res.json();
  return unwrapPaginated<T>(json) as T;
}

export const funeralLogisticsApi = {
  listExpenses: (funeralId: string) => request<FuneralExpense[]>(`/funerals/${funeralId}/expenses/`),

  expenseSummary: (funeralId: string) => request<ExpenseSummary>(`/funerals/${funeralId}/expenses/summary/`),

  /**
   * "Item, Quantity, Unit price, Total amount, Supplier, Buyer... Notes."
   * Either `amount` alone, or `quantity` + `unit_price` together (the
   * backend computes the total) — see funeral_logistics.services.record_expense.
   * Invoice file upload isn't wired in here yet — the backend already
   * accepts it (a real FileField, tested with multipart uploads
   * directly), but this JSON-only client doesn't send files; that's a
   * genuine, known gap, not something silently skipped.
   */
  recordExpense: (
    funeralId: string,
    input: {
      description: string; category: ExpenseCategory; incurred_on: string;
      amount?: string; quantity?: number; unit_price?: string;
      item_name?: string; supplier_name?: string; buyer_id?: string; notes?: string;
      payment_method?: ExpensePaymentMethod;
    }
  ) => request<FuneralExpense>(`/funerals/${funeralId}/expenses/`, { method: "POST", body: JSON.stringify(input) }),

  decideExpenseStatus: (funeralId: string, expenseId: string, status: ExpenseStatus, amountPaid?: string) =>
    request<FuneralExpense>(`/funerals/${funeralId}/expenses/${expenseId}/status/`, {
      method: "POST",
      body: JSON.stringify({ status, amount_paid: amountPaid }),
    }),

  /** "Credit payments create liabilities" — every unsettled expense across the whole community. */
  listLiabilities: () => request<FuneralExpense[]>(`/expenses/liabilities/`),

  /** "The funeral expenses should have its own link to be one of the multiple tasks" — every active funeral's real total, not just outstanding/credit ones. */
  expensesOverview: () =>
    request<{
      funeral_id: string; deceased_name: string; deceased_family_name: string;
      expense_count: number; cancelled_count: number; total_expenses: string; total_owed: string;
      by_category: Record<string, string>;
    }[]>(`/expenses/overview/`),

  listAttendance: (funeralId: string) => request<FuneralAttendanceRecord[]>(`/funerals/${funeralId}/attendance/`),

  attendanceSummary: (funeralId: string) => request<AttendanceSummary>(`/funerals/${funeralId}/attendance/summary/`),

  recordAttendance: (funeralId: string, input: { member_id?: string; guest_name?: string }) =>
    request<FuneralAttendanceRecord>(`/funerals/${funeralId}/attendance/`, { method: "POST", body: JSON.stringify(input) }),

  financialOverview: (funeralId: string) => request<FinancialOverview>(`/funerals/${funeralId}/financial-overview/`),
};
