"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { membersApi } from "@/lib/api/members";
import { useMemberRateOverrides, useSetMemberRateOverrides } from "@/lib/hooks/useFunerals";
import { formatCedis } from "@/lib/formatCedis";

/**
 * "The family head and secretary of the deceased family can set an
 * amount for each member [of their own family] have to pay." Only
 * meaningful while the funeral is still awaiting approval — the
 * backend refuses this the moment it activates (obligations already
 * exist by then). If the signed-in person isn't this family's own head
 * or secretary, the backend's 403 surfaces as a quiet, honest "you
 * don't have access" rather than a broken form.
 */
export function MemberRateOverridesPanel({ funeralId, deceasedFamilyId }: { funeralId: string; deceasedFamilyId: string }) {
  const { data: familyMembers } = useQuery({
    queryKey: ["family-members", deceasedFamilyId],
    queryFn: () => membersApi.list({ family: deceasedFamilyId }),
    enabled: Boolean(deceasedFamilyId),
  });
  const { data: existingOverrides, isError } = useMemberRateOverrides(funeralId);
  const setOverrides = useSetMemberRateOverrides(funeralId);

  const [amounts, setAmounts] = useState<Record<string, string>>({});
  const [expanded, setExpanded] = useState(false);

  if (isError) return null; // not this family's officer — say nothing rather than show a broken panel

  const existingByMember = Object.fromEntries((existingOverrides ?? []).map((o) => [o.member, o.amount]));

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const changed = Object.fromEntries(Object.entries(amounts).filter(([, v]) => v.trim() !== ""));
    if (Object.keys(changed).length === 0) return;
    setOverrides.mutate(changed, { onSuccess: () => setAmounts({}) });
  };

  if (!expanded) {
    return (
      <button onClick={() => setExpanded(true)} className="mt-3 text-xs text-[var(--forest)] hover:underline">
        Set a custom amount per family member (optional)
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="mt-3 rounded-sm bg-[var(--surface)] p-3">
      <p className="text-xs text-[var(--ink-soft)]">
        Overrides the usual family rate for just the people you set an amount for here — everyone
        else in the family still pays the normal head/uncle/nephew/woman rate.
      </p>
      <ul className="mt-2 space-y-1.5">
        {familyMembers?.map((m) => (
          <li key={m.id} className="flex items-center justify-between gap-2 text-sm">
            <span className="truncate">{m.full_name}</span>
            <div className="flex shrink-0 items-center gap-2">
              {existingByMember[m.id] && (
                <span className="font-mono text-xs text-[var(--gold)]">currently {formatCedis(existingByMember[m.id])}</span>
              )}
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="GH₵"
                value={amounts[m.id] ?? ""}
                onChange={(e) => setAmounts((prev) => ({ ...prev, [m.id]: e.target.value }))}
                className="w-24 rounded-sm border border-[var(--rule)] bg-white px-2 py-1 text-xs outline-none focus:border-[var(--forest)]"
              />
            </div>
          </li>
        ))}
      </ul>
      {setOverrides.isError && <p className="mt-2 text-xs text-[var(--clay-red)]">{(setOverrides.error as Error).message}</p>}
      <div className="mt-3 flex gap-2">
        <button
          type="submit"
          disabled={setOverrides.isPending}
          className="rounded-sm bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
        >
          {setOverrides.isPending ? "Saving…" : "Save amounts"}
        </button>
        <button type="button" onClick={() => setExpanded(false)} className="text-xs text-[var(--ink-soft)]">
          Close
        </button>
      </div>
    </form>
  );
}
