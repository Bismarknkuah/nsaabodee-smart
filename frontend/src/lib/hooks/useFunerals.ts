import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { funeralsApi } from "@/lib/api/funerals";
import type { PaymentStatus, RateType } from "@/types/funeral";

export function useFunerals(status: "active" | "closed" | "cancelled" | "pending_approval" | "all" = "active") {
  return useQuery({ queryKey: ["funerals", status], queryFn: () => funeralsApi.list(status) });
}

export function useFuneral(id: string) {
  return useQuery({ queryKey: ["funeral", id], queryFn: () => funeralsApi.get(id), enabled: Boolean(id) });
}

export function useFuneralSummary(id: string) {
  return useQuery({
    queryKey: ["funeral-summary", id],
    queryFn: () => funeralsApi.summary(id),
    enabled: Boolean(id),
    refetchInterval: 15_000, // collectors are recording payments live; keep totals fresh
  });
}

export function useFuneralObligations(
  id: string,
  filters?: { rate_type?: RateType; payment_status?: PaymentStatus }
) {
  return useQuery({
    queryKey: ["funeral-obligations", id, filters],
    queryFn: () => funeralsApi.obligations(id, filters),
    enabled: Boolean(id),
  });
}

export function useFuneralActions(funeralId: string) {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["funeral-summary", funeralId] });
    qc.invalidateQueries({ queryKey: ["funeral-obligations", funeralId] });
  };

  const recordPayment = useMutation({
    mutationFn: (input: { obligationId: string; amount: string; method: "cash" | "mobile_money" | "bank" | "other" }) =>
      funeralsApi.recordPayment(funeralId, input.obligationId, {
        amount: input.amount,
        method: input.method,
        client_op_id: crypto.randomUUID(),
      }),
    onSuccess: invalidate,
  });

  const close = useMutation({
    mutationFn: () => funeralsApi.close(funeralId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["funerals"] }),
  });

  return { recordPayment, close };
}

export function useCreateFuneral() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: funeralsApi.create,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["funerals"] }),
  });
}

export function useRequestFuneralOpening() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: funeralsApi.requestOpening,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["funerals"] }),
  });
}

export function useFuneralApprovalProgress(funeralId: string) {
  return useQuery({
    queryKey: ["funeral-approval-progress", funeralId],
    queryFn: () => funeralsApi.approvalProgress(funeralId),
    enabled: Boolean(funeralId),
  });
}

export function useFuneralOpeningActions(funeralId: string) {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["funerals"] });
    qc.invalidateQueries({ queryKey: ["funeral-approval-progress", funeralId] });
    qc.invalidateQueries({ queryKey: ["funeral", funeralId] });
  };
  const approve = useMutation({ mutationFn: () => funeralsApi.approveOpening(funeralId), onSuccess: invalidate });
  const reject = useMutation({ mutationFn: () => funeralsApi.rejectOpening(funeralId), onSuccess: invalidate });
  return { approve, reject };
}

export function useMemberRateOverrides(funeralId: string) {
  return useQuery({
    queryKey: ["member-rate-overrides", funeralId],
    queryFn: () => funeralsApi.listMemberRateOverrides(funeralId),
    enabled: Boolean(funeralId),
    retry: false,
  });
}

export function useSetMemberRateOverrides(funeralId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (overrides: Record<string, string>) => funeralsApi.setMemberRateOverrides(funeralId, overrides),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["member-rate-overrides", funeralId] }),
  });
}

export function useDeskAssignments(funeralId: string) {
  return useQuery({
    queryKey: ["desk-assignments", funeralId],
    queryFn: () => funeralsApi.listDeskAssignments(funeralId),
    enabled: Boolean(funeralId),
    retry: false,
  });
}

export function useAssignDeskWorker(funeralId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: Parameters<typeof funeralsApi.assignDeskWorker>[1]) => funeralsApi.assignDeskWorker(funeralId, input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["desk-assignments", funeralId] }),
  });
}

export function useRemoveDeskAssignment(funeralId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (assignmentId: string) => funeralsApi.removeDeskAssignment(funeralId, assignmentId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["desk-assignments", funeralId] }),
  });
}
