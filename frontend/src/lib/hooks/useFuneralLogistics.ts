import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { funeralLogisticsApi } from "@/lib/api/funeralLogistics";

export function useExpenses(funeralId: string) {
  return useQuery({ queryKey: ["expenses", funeralId], queryFn: () => funeralLogisticsApi.listExpenses(funeralId), enabled: Boolean(funeralId) });
}

export function useExpenseSummary(funeralId: string) {
  return useQuery({ queryKey: ["expense-summary", funeralId], queryFn: () => funeralLogisticsApi.expenseSummary(funeralId), enabled: Boolean(funeralId) });
}

export function useAttendance(funeralId: string) {
  return useQuery({ queryKey: ["attendance", funeralId], queryFn: () => funeralLogisticsApi.listAttendance(funeralId), enabled: Boolean(funeralId) });
}

export function useAttendanceSummary(funeralId: string) {
  return useQuery({ queryKey: ["attendance-summary", funeralId], queryFn: () => funeralLogisticsApi.attendanceSummary(funeralId), enabled: Boolean(funeralId) });
}

export function useFinancialOverview(funeralId: string) {
  return useQuery({ queryKey: ["financial-overview", funeralId], queryFn: () => funeralLogisticsApi.financialOverview(funeralId), enabled: Boolean(funeralId) });
}

/** "Credit payments create liabilities" — every unsettled expense across the whole community. */
export function useLiabilities() {
  return useQuery({ queryKey: ["expense-liabilities"], queryFn: funeralLogisticsApi.listLiabilities });
}

export function useExpensesOverview() {
  return useQuery({ queryKey: ["expenses-overview"], queryFn: funeralLogisticsApi.expensesOverview });
}

export function useFuneralLogisticsActions(funeralId: string) {
  const qc = useQueryClient();

  const recordExpense = useMutation({
    mutationFn: (input: Parameters<typeof funeralLogisticsApi.recordExpense>[1]) =>
      funeralLogisticsApi.recordExpense(funeralId, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["expenses", funeralId] });
      qc.invalidateQueries({ queryKey: ["expense-summary", funeralId] });
      qc.invalidateQueries({ queryKey: ["financial-overview", funeralId] });
    },
  });

  const decideExpenseStatus = useMutation({
    mutationFn: ({ expenseId, status, amountPaid }: { expenseId: string; status: Parameters<typeof funeralLogisticsApi.decideExpenseStatus>[2]; amountPaid?: string }) =>
      funeralLogisticsApi.decideExpenseStatus(funeralId, expenseId, status, amountPaid),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["expenses", funeralId] });
      qc.invalidateQueries({ queryKey: ["expense-summary", funeralId] });
      qc.invalidateQueries({ queryKey: ["expense-liabilities"] });
    },
  });

  const recordAttendance = useMutation({
    mutationFn: (input: Parameters<typeof funeralLogisticsApi.recordAttendance>[1]) =>
      funeralLogisticsApi.recordAttendance(funeralId, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["attendance", funeralId] });
      qc.invalidateQueries({ queryKey: ["attendance-summary", funeralId] });
    },
  });

  return { recordExpense, decideExpenseStatus, recordAttendance };
}
