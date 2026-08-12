import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { familyFundsApi } from "@/lib/api/familyFunds";
import type { FundPaymentMethod } from "@/types/familyFund";

export function useFamilyFunds(familyId: string) {
  return useQuery({
    queryKey: ["family-funds", familyId],
    queryFn: () => familyFundsApi.list(familyId),
    enabled: Boolean(familyId),
    retry: false,
  });
}

export function useCreateFamilyFund(familyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, description }: { name: string; description?: string }) =>
      familyFundsApi.create(familyId, name, description),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["family-funds", familyId] }),
  });
}

export function useFundContributions(familyId: string, fundId: string) {
  return useQuery({
    queryKey: ["fund-contributions", familyId, fundId],
    queryFn: () => familyFundsApi.listContributions(familyId, fundId),
    enabled: Boolean(familyId && fundId),
  });
}

export function useFundSummary(familyId: string, fundId: string) {
  return useQuery({
    queryKey: ["fund-summary", familyId, fundId],
    queryFn: () => familyFundsApi.summary(familyId, fundId),
    enabled: Boolean(familyId && fundId),
  });
}

export function useContributeToFund(familyId: string, fundId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { member_id: string; amount: string; payment_method?: FundPaymentMethod }) =>
      familyFundsApi.contribute(familyId, fundId, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["fund-contributions", familyId, fundId] });
      qc.invalidateQueries({ queryKey: ["fund-summary", familyId, fundId] });
    },
  });
}

export function useAssignFamilyOfficer(familyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ memberId, officerRole }: { memberId: string; officerRole: "secretary" | "treasurer" }) =>
      familyFundsApi.assignOfficer(familyId, memberId, officerRole),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["family", familyId] }),
  });
}

export function useFamilyOfficerPositions(familyId: string) {
  return useQuery({ queryKey: ["family-officer-positions", familyId], queryFn: () => familyFundsApi.listOfficerPositions(familyId) });
}

export function useAppointFamilyOfficerPosition(familyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ memberId, title }: { memberId: string; title: string }) => familyFundsApi.appointOfficerPosition(familyId, memberId, title),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["family-officer-positions", familyId] }),
  });
}

export function useRemoveFamilyOfficerPosition(familyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (positionId: string) => familyFundsApi.removeOfficerPosition(familyId, positionId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["family-officer-positions", familyId] }),
  });
}

// --- Family Funeral Expense Tracking ---
import { familyFuneralExpensesApi } from "@/lib/api/familyFunds";

export function useFuneralExpenses(familyId: string, funeralEventId?: string) {
  return useQuery({
    queryKey: ["family-funeral-expenses", familyId, funeralEventId],
    queryFn: () => familyFuneralExpensesApi.list(familyId, funeralEventId),
    enabled: Boolean(familyId),
    retry: false,
  });
}

export function useExpenditureSummary(familyId: string, funeralEventId?: string) {
  return useQuery({
    queryKey: ["family-funeral-expenditure-summary", familyId, funeralEventId],
    queryFn: () => familyFuneralExpensesApi.summary(familyId, funeralEventId),
    enabled: Boolean(familyId),
    retry: false,
  });
}

export function useRecordFuneralExpense(familyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: Parameters<typeof familyFuneralExpensesApi.record>[1]) =>
      familyFuneralExpensesApi.record(familyId, input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["family-funeral-expenses", familyId] });
      qc.invalidateQueries({ queryKey: ["family-funeral-expenditure-summary", familyId] });
    },
  });
}

export function useDecideFuneralExpense(familyId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ expenseId, action, reason }: { expenseId: string; action: "approve" | "reject"; reason?: string }) =>
      familyFuneralExpensesApi.decide(familyId, expenseId, action, reason),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["family-funeral-expenses", familyId] });
      qc.invalidateQueries({ queryKey: ["family-funeral-expenditure-summary", familyId] });
    },
  });
}

// --- Family Financial Overview (Fund vs. Expenses, net position) ---
import { familyFinancialOverviewApi } from "@/lib/api/familyFunds";

export function useFamilyFinancialOverview(familyId: string, funeralEventId?: string) {
  return useQuery({
    queryKey: ["family-financial-overview", familyId, funeralEventId],
    queryFn: () => familyFinancialOverviewApi.get(familyId, funeralEventId),
    enabled: Boolean(familyId),
    retry: false,
  });
}
