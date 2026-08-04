"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useDonationAccounts, useRegisterDonationAccount } from "@/lib/hooks/useGifts";
import { useFuneral } from "@/lib/hooks/useFunerals";
import { membersApi } from "@/lib/api/members";

/**
 * "Deceased members can let them open a temporary donation account for
 * them to receive their gifts... more than 1 person can receive... all
 * those who know will receive donations have to register." This is
 * that registration: a name-only list (never money) — see
 * GiftLedgerPanel for why it's deliberately visible to everyone,
 * unlike the actual gift totals.
 */
export function DonationAccountsPanel({ funeralId }: { funeralId: string }) {
  const { data: funeral } = useFuneral(funeralId);
  const { data: accounts, isLoading } = useDonationAccounts(funeralId);
  const register = useRegisterDonationAccount(funeralId);
  const [query, setQuery] = useState("");
  const { data: memberResults } = useQuery({
    queryKey: ["donation-account-member-search", query],
    queryFn: () => membersApi.list({ search: query }),
    enabled: query.trim().length >= 2,
  });

  const alreadyRegisteredIds = new Set(accounts?.map((a) => a.member));

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
        Anyone can see who&apos;s registered — names only, never amounts. A cashier picks from
        this list when recording a gift someone wants to give to a specific person.
      </p>

      <ul className="mt-3 flex flex-wrap gap-2">
        {isLoading && <li className="text-xs text-[var(--ink-soft)]">Loading…</li>}
        {accounts?.length === 0 && <li className="text-xs text-[var(--ink-soft)]">Nobody registered yet.</li>}
        {accounts?.map((a) => (
          <li key={a.id} className="rounded-full bg-white px-3 py-1 text-xs font-medium">
            {a.member_name}
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
