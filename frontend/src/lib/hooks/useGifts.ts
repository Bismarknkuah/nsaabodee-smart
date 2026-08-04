import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { giftsApi } from "@/lib/api/gifts";
import type { DonorCategory } from "@/types/gift";

export function useGiftDonations(funeralId: string, category?: DonorCategory) {
  return useQuery({
    queryKey: ["gifts", funeralId, category],
    queryFn: () => giftsApi.list(funeralId, category),
    enabled: Boolean(funeralId),
    // A 403 here just means "you're not this family's head / admin" —
    // that's an expected, ordinary state for most committee roles now,
    // not a bug to retry into.
    retry: false,
  });
}

/** "Unless required for reconciliation, auditing, or legal compliance" — reveals real donor names for a temporary event; every call is audit-logged server-side. */
export function useGiftDonationsReconciliation(funeralId: string, reason: string) {
  return useQuery({
    queryKey: ["gifts-reconciliation", funeralId, reason],
    queryFn: () => giftsApi.listWithReconciliation(funeralId, reason),
    enabled: Boolean(funeralId) && Boolean(reason),
    retry: false,
  });
}

export function useGiftSummary(funeralId: string) {
  return useQuery({ queryKey: ["gift-summary", funeralId], queryFn: () => giftsApi.summary(funeralId), enabled: Boolean(funeralId), retry: false });
}

export function useGiftCategoryBreakdown(funeralId: string) {
  return useQuery({
    queryKey: ["gift-category-breakdown", funeralId],
    queryFn: () => giftsApi.categoryBreakdown(funeralId),
    enabled: Boolean(funeralId),
    retry: false,
  });
}

export function useRecordGift(funeralId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: Parameters<typeof giftsApi.record>[1]) =>
      giftsApi.record(funeralId, { ...input, client_op_id: crypto.randomUUID() }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["gifts", funeralId] });
      qc.invalidateQueries({ queryKey: ["gift-summary", funeralId] });
      qc.invalidateQueries({ queryKey: ["gift-category-breakdown", funeralId] });
      qc.invalidateQueries({ queryKey: ["donation-accounts", funeralId] });
    },
  });
}

// --- Donation Accounts ("temporary donation account") ---

export function useDonationAccounts(funeralId: string) {
  return useQuery({
    queryKey: ["donation-accounts", funeralId],
    queryFn: () => giftsApi.listDonationAccounts(funeralId),
    enabled: Boolean(funeralId),
  });
}

export function useRegisterDonationAccount(funeralId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (memberId: string) => giftsApi.registerDonationAccount(funeralId, memberId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["donation-accounts", funeralId] }),
  });
}

/** The Family Head's own approval queue — "activated when the family heads approve it." */
export function usePendingDonationAccounts(enabled = true) {
  return useQuery({ queryKey: ["pending-donation-accounts"], queryFn: giftsApi.pendingDonationAccounts, retry: false, enabled });
}

export function useApproveDonationAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (registrationId: string) => giftsApi.approveDonationAccount(registrationId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["pending-donation-accounts"] }),
  });
}

// --- "Any amount paid should reflect on the person dashboard" ---

export function useMyDonationsReceived() {
  return useQuery({ queryKey: ["my-donations-received"], queryFn: giftsApi.myDonationsReceived });
}

// --- "After the funeral all should be able to print receipts to all those who received donations" ---

export function useAllReceiversStatement(funeralId: string) {
  return useQuery({
    queryKey: ["all-receivers-statement", funeralId],
    queryFn: () => giftsApi.allReceiversStatement(funeralId),
    enabled: Boolean(funeralId),
    retry: false,
  });
}
