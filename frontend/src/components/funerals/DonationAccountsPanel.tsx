"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAllDonationAccountsIncludingPending, useRegisterDonationAccount, useApproveDonationAccount } from "@/lib/hooks/useGifts";
import { useFuneral } from "@/lib/hooks/useFunerals";
import { useFamilies } from "@/lib/hooks/useFamilies";
import { membersApi } from "@/lib/api/members";
import { useAuthStore } from "@/store/authStore";

/**
 * "Deceased members can let them open a temporary donation account for
 * them to receive their gifts... more than 1 person can receive... all
 * those who know will receive donations have to register." This is
 * that registration: a name-only list (never money) — see
 * GiftLedgerPanel for why it's deliberately visible to everyone,
 * unlike the actual gift totals.
 *
 * A pending registration (anyone but the Family Head registering
 * someone starts it pending — see the donation-receiving permission
 * overhaul) is shown distinctly here, not silently absent until
 * approved — the family head, viewing this same panel, can approve it
 * directly rather than needing to go find it on a separate page.
 */
export function DonationAccountsPanel({ funeralId }: { funeralId: string }) {
  const { data: funeral } = useFuneral(funeralId);
  const { data: accounts, isLoading } = useAllDonationAccountsIncludingPending(funeralId);
  const register = useRegisterDonationAccount(funeralId);
  const approve = useApproveDonationAccount();
  const user = useAuthStore((s) => s.user);
  const [query, setQuery] = useState("");
  const { data: memberResults } = useQuery({
    queryKey: ["donation-account-member-search", query],
    queryFn: () => membersApi.list({ search: query }),
    enabled: query.trim().length >= 2,
  });

  const { data: families } = useFamilies(false);
  const alreadyRegisteredIds = new Set(accounts?.map((a) => a.member));
  // The Family Head reviewing this panel can approve directly, if this
  // is their own family's funeral — the same jurisdiction check the
  // backend itself enforces. Same pattern as RegisterMemberDialog for
  // deriving "which family does this Family Head actually lead."
  const ownFamily = user?.role === "family_head" ? families?.find((f) => f.family_head?.id === user?.linked_member_id) : undefined;
  const canApprove = Boolean(ownFamily && funeral && ownFamily.id === funeral.deceased_family);

  return (
    <div className="rounded-sm bg-[var(--surface)] p-4">
      {funeral && (
        <p className="text-xs font-medium" style={{ color: "var(--violet)" }}>
          Activating donation accounts for {funeral.deceased_name}&apos;s funeral — died{" "}
          {new Date(funeral.date_of_death).toLocaleDateString()}. Once registered, the cashier
          won&apos;t need to re-enter these details for every gift.
        </p>
      )}
      <p className="mt-2 text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">
        Registered to receive donations
      </p>
      <p className="mt-1 text-xs text-[var(--ink-soft)]">
        Anyone can see who&apos;s registered — names only, never amounts. A pending request
        (dashed) isn&apos;t selectable for a gift yet — only the family head&apos;s approval
        activates it.
      </p>

      <ul className="mt-3 flex flex-wrap gap-2">
        {isLoading && <li className="text-xs text-[var(--ink-soft)]">Loading…</li>}
        {accounts?.length === 0 && <li className="text-xs text-[var(--ink-soft)]">Nobody registered yet.</li>}
        {accounts?.map((a) => (
          <li
            key={a.id}
            className={`flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ${
              a.is_active ? "bg-white" : "border border-dashed border-[var(--gold)] bg-[var(--gold)]/10 text-[var(--ink)]"
            }`}
          >
            {a.member_name}
            {!a.is_active && <span className="text-[var(--gold)]">· pending</span>}
            {!a.is_active && canApprove && (
              <button
                onClick={() => approve.mutate(a.id)}
                disabled={approve.isPending}
                className="rounded-full border border-[var(--forest)] px-2 py-0.5 text-[10px] font-medium text-[var(--forest)] disabled:opacity-50"
              >
                Approve
              </button>
            )}
          </li>
        ))}
      </ul>

      <div className="mt-3">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search a member to register…"
          className="w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
        />
        {memberResults && memberResults.length > 0 && (
          <ul className="mt-2 max-h-32 divide-y divide-[var(--rule)] overflow-y-auto rounded-sm bg-white">
            {memberResults.map((m) => {
              const already = alreadyRegisteredIds.has(m.id);
              return (
                <li key={m.id} className="flex items-center justify-between px-3 py-2 text-sm">
                  <span>{m.full_name}</span>
                  <button
                    disabled={already || register.isPending}
                    onClick={() => {
                      register.mutate(m.id, { onSuccess: () => setQuery("") });
                    }}
                    className="rounded-sm border border-[var(--rule)] px-2 py-1 text-xs font-medium disabled:opacity-50 hover:border-[var(--forest)] hover:text-[var(--forest)]"
                  >
                    {already ? "Already registered" : "Register"}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        {register.isError && <p className="mt-1 text-xs text-[var(--clay-red)]">{register.error.message}</p>}
      </div>
    </div>
  );
}

