import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { contributionRulesApi } from "@/lib/api/contributionRules";

const KEY = ["contribution-rules"] as const;

export function useContributionRules() {
  return useQuery({ queryKey: KEY, queryFn: contributionRulesApi.get });
}

export function useContributionRuleActions() {
  const qc = useQueryClient();
  const setData = (data: Awaited<ReturnType<typeof contributionRulesApi.get>>) => qc.setQueryData(KEY, data);

  const updateGeneralRates = useMutation({
    mutationFn: ({ male, female, reason }: { male: string; female: string; reason?: string }) =>
      contributionRulesApi.updateGeneralRates(male, female, reason),
    onSuccess: setData,
  });

  const updateFamilyTierRates = useMutation({
    mutationFn: contributionRulesApi.updateFamilyTierRates,
    onSuccess: setData,
  });

  const setStatusExemption = useMutation({
    mutationFn: ({ status, isExempt }: { status: string; isExempt: boolean }) =>
      contributionRulesApi.setStatusExemption(status, isExempt),
    onSuccess: setData,
  });

  const updateDefaulterThresholds = useMutation({
    mutationFn: ({ warning, highWarning, flag }: { warning: number; highWarning: number; flag: number }) =>
      contributionRulesApi.updateDefaulterThresholds(warning, highWarning, flag),
    onSuccess: setData,
  });

  return { updateGeneralRates, updateFamilyTierRates, setStatusExemption, updateDefaulterThresholds };
}

export function usePreviewObligations() {
  return useMutation({ mutationFn: contributionRulesApi.preview });
}
