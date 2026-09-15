import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { welfareApi } from "@/lib/api/welfare";

export function useContributionCategories() {
  return useQuery({ queryKey: ["welfare-categories"], queryFn: welfareApi.listCategories });
}

export function useCampaigns() {
  return useQuery({ queryKey: ["welfare-campaigns"], queryFn: welfareApi.listCampaigns });
}

export function useCampaignObligations(campaignId: string) {
  return useQuery({
    queryKey: ["welfare-obligations", campaignId],
    queryFn: () => welfareApi.listObligations(campaignId),
    enabled: Boolean(campaignId),
  });
}

export function useWelfareActions() {
  const qc = useQueryClient();

  const createCategory = useMutation({
    mutationFn: welfareApi.createCategory,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["welfare-categories"] }),
  });

  const initiateCommunityCampaign = useMutation({
    mutationFn: welfareApi.initiateCommunityCampaign,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["welfare-campaigns"] }),
  });

  const initiateFamilyCampaign = useMutation({
    mutationFn: ({ familyId, input }: { familyId: string; input: Parameters<typeof welfareApi.initiateFamilyCampaign>[1] }) =>
      welfareApi.initiateFamilyCampaign(familyId, input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["welfare-campaigns"] }),
  });

  const decideCampaign = useMutation({
    mutationFn: ({ campaignId, approve }: { campaignId: string; approve: boolean }) => welfareApi.decideCampaign(campaignId, approve),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["welfare-campaigns"] }),
  });

  const adminApproveCampaign = useMutation({
    mutationFn: ({ campaignId, approve }: { campaignId: string; approve?: boolean }) => welfareApi.adminApproveCampaign(campaignId, approve ?? true),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["welfare-campaigns"] }),
  });

  const recordPayment = useMutation({
    mutationFn: ({ obligationId, input, campaignId }: { obligationId: string; input: Parameters<typeof welfareApi.recordPayment>[1]; campaignId: string }) =>
      welfareApi.recordPayment(obligationId, input),
    onSuccess: (_data, variables) => qc.invalidateQueries({ queryKey: ["welfare-obligations", variables.campaignId] }),
  });

  return { createCategory, initiateCommunityCampaign, initiateFamilyCampaign, decideCampaign, adminApproveCampaign, recordPayment };
}
