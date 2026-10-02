import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { aiApi } from "@/lib/api/aiFeatures";

export function usePredictedCollections(funeralId: string) {
  return useQuery({
    queryKey: ["predicted-collections", funeralId],
    queryFn: () => aiApi.predictCollections(funeralId),
    enabled: Boolean(funeralId),
  });
}

export function useInactiveMembers(inactiveDays: number) {
  return useQuery({
    queryKey: ["inactive-members", inactiveDays],
    queryFn: () => aiApi.inactiveMembers(inactiveDays),
  });
}

export function useFuzzySearch(query: string) {
  return useQuery({
    queryKey: ["fuzzy-search", query],
    queryFn: () => aiApi.search(query),
    enabled: query.trim().length >= 2,
  });
}

export function useSummarizeMeeting() {
  return useMutation({ mutationFn: aiApi.summarizeMeeting });
}

export function useSuspiciousTransactions() {
  return useQuery({ queryKey: ["suspicious-transactions"], queryFn: aiApi.suspiciousTransactions });
}

export function useReviewSuspiciousTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, reviewStatus }: { id: string; reviewStatus: "confirmed" | "dismissed" }) =>
      aiApi.reviewSuspiciousTransaction(id, reviewStatus),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["suspicious-transactions"] }),
  });
}
