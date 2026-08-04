import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { familiesApi } from "@/lib/api/families";

const FAMILIES_KEY = ["families"] as const;

export function useFamilies(includeInactive = false) {
  return useQuery({
    queryKey: [...FAMILIES_KEY, { includeInactive }],
    queryFn: () => familiesApi.list(includeInactive),
  });
}

export function useFamilyAuditLog(familyId: string | null) {
  return useQuery({
    queryKey: ["family-audit-log", familyId],
    queryFn: () => familiesApi.auditLogs(familyId as string),
    enabled: Boolean(familyId),
  });
}

/**
 * One mutation hook per action rather than a single generic mutate() —
 * this keeps optimistic-update / error-toast wiring specific to each
 * action's meaning (e.g. a failed merge should never silently look like
 * a failed rename in a toast).
 */
export function useFamilyActions() {
  const qc = useQueryClient();
  const invalidate = () => qc.invalidateQueries({ queryKey: FAMILIES_KEY });

  const create = useMutation({
    mutationFn: familiesApi.create,
    onSuccess: invalidate,
  });

  const registerWithHead = useMutation({
    mutationFn: familiesApi.registerWithHead,
    onSuccess: invalidate,
  });

  const rename = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => familiesApi.rename(id, name),
    onSuccess: invalidate,
  });

  const merge = useMutation({
    mutationFn: ({ sourceId, targetId }: { sourceId: string; targetId: string }) =>
      familiesApi.merge(sourceId, targetId),
    onSuccess: invalidate,
  });

  const deactivate = useMutation({
    mutationFn: (id: string) => familiesApi.deactivate(id),
    onSuccess: invalidate,
  });

  const reactivate = useMutation({
    mutationFn: (id: string) => familiesApi.reactivate(id),
    onSuccess: invalidate,
  });

  const remove = useMutation({
    mutationFn: ({ id, force }: { id: string; force?: boolean }) => familiesApi.remove(id, force),
    onSuccess: invalidate,
  });

  const transferMembers = useMutation({
    mutationFn: ({ targetId, memberIds }: { targetId: string; memberIds: string[] }) =>
      familiesApi.transferMembers(targetId, memberIds),
    onSuccess: invalidate,
  });

  const assignHead = useMutation({
    mutationFn: ({ id, memberId }: { id: string; memberId: string }) =>
      familiesApi.assignHead(id, memberId),
    onSuccess: invalidate,
  });

  const recommendRate = useMutation({
    mutationFn: ({ id, amount }: { id: string; amount: string }) => familiesApi.recommendRate(id, amount),
    onSuccess: invalidate,
  });

  const approveRate = useMutation({
    mutationFn: ({ id, amount }: { id: string; amount?: string }) => familiesApi.approveRate(id, amount),
    onSuccess: invalidate,
  });

  const rejectRate = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) => familiesApi.rejectRate(id, reason),
    onSuccess: invalidate,
  });

  return {
    create, registerWithHead, rename, merge, deactivate, reactivate, remove, transferMembers, assignHead,
    recommendRate, approveRate, rejectRate,
  };
}
