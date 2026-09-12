import { useQuery } from "@tanstack/react-query";
import { reportsApi } from "@/lib/api/reports";

export function useDailyReport(date: string) {
  return useQuery({ queryKey: ["report-daily", date], queryFn: () => reportsApi.daily(date) });
}

export function useWeeklyReport(weekStart: string) {
  return useQuery({ queryKey: ["report-weekly", weekStart], queryFn: () => reportsApi.weekly(weekStart) });
}

export function useMonthlyReport(year: number, month: number) {
  return useQuery({ queryKey: ["report-monthly", year, month], queryFn: () => reportsApi.monthly(year, month) });
}

export function useAnnualReport(year: number) {
  return useQuery({ queryKey: ["report-annual", year], queryFn: () => reportsApi.annual(year) });
}

export function useExpenseStatement(startDate: string, endDate: string) {
  return useQuery({ queryKey: ["report-expenses", startDate, endDate], queryFn: () => reportsApi.expenseStatement(startDate, endDate) });
}

export function useOutstandingMembers() {
  return useQuery({ queryKey: ["report-outstanding-members"], queryFn: () => reportsApi.outstandingMembers() });
}

export function useFamilyStatement(familyId: string) {
  return useQuery({ queryKey: ["report-family-statement", familyId], queryFn: () => reportsApi.familyStatement(familyId), enabled: Boolean(familyId) });
}

export function useMyReceipts() {
  return useQuery({ queryKey: ["my-receipts"], queryFn: () => reportsApi.myReceipts() });
}

export function useMyOutstandingObligations() {
  return useQuery({ queryKey: ["my-obligations"], queryFn: () => reportsApi.myOutstandingObligations() });
}

export function useMemberOutstandingObligations(memberId: string | null) {
  return useQuery({
    queryKey: ["member-outstanding-obligations", memberId],
    queryFn: () => reportsApi.memberOutstandingObligations(memberId as string),
    enabled: Boolean(memberId),
  });
}
