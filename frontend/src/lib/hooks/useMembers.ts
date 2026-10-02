import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { membersApi } from "@/lib/api/members";
import type { DefaulterTier, Member, MemberStatus } from "@/types/member";

export function useMembers(filters?: { search?: string; family?: string; status?: MemberStatus; defaulter_tier?: DefaulterTier; gender?: "male" | "female"; sort_by?: string }) {
  return useQuery({ queryKey: ["members", filters], queryFn: () => membersApi.list(filters) });
}

export function useMember(id: string) {
  return useQuery({ queryKey: ["member", id], queryFn: () => membersApi.get(id), enabled: Boolean(id) });
}

export function useMemberCard(id: string) {
  return useQuery({ queryKey: ["member-card", id], queryFn: () => membersApi.card(id), enabled: Boolean(id) });
}

export function useDefaulters() {
  return useQuery({ queryKey: ["defaulters"], queryFn: () => membersApi.defaulters() });
}

export function useMemberActions() {
  const qc = useQueryClient();
  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["members"] });
    qc.invalidateQueries({ queryKey: ["defaulters"] });
  };

  const register = useMutation({ mutationFn: membersApi.register, onSuccess: invalidate });

  const update = useMutation({
    mutationFn: ({ id, fields }: { id: string; fields: Partial<Member> }) => membersApi.update(id, fields),
    onSuccess: invalidate,
  });

  const linkUser = useMutation({
    mutationFn: ({ id, username }: { id: string; username: string }) => membersApi.linkUser(id, username),
    onSuccess: (_, { id }) => qc.invalidateQueries({ queryKey: ["member", id] }),
  });

  const assignRole = useMutation({
    mutationFn: ({ id, role, username, password }: { id: string; role: string; username?: string; password?: string }) =>
      membersApi.assignRole(id, { role, username, password }),
    onSuccess: (_, { id }) => qc.invalidateQueries({ queryKey: ["member", id] }),
  });

  const revokeRole = useMutation({
    mutationFn: (id: string) => membersApi.revokeRole(id),
    onSuccess: (_, id) => qc.invalidateQueries({ queryKey: ["member", id] }),
  });

  const transferToTownElder = useMutation({
    mutationFn: ({ id, title }: { id: string; title: "chief" | "queen_mother" | "linguist" | "other" }) =>
      membersApi.transferToTownElder(id, title),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: ["member", id] });
      qc.invalidateQueries({ queryKey: ["town-elders-ledger"] });
    },
  });

  return { register, update, linkUser, assignRole, revokeRole, transferToTownElder };
}

/** 'If he doesn't get change, money balance should be credited to the member's wallet.' */
export function useMemberWallet(memberId: string, enabled = true) {
  return useQuery({ queryKey: ["member-wallet", memberId], queryFn: () => membersApi.wallet(memberId), enabled: Boolean(memberId) && enabled });
}
