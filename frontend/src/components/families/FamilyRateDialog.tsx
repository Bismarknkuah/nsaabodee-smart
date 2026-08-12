"use client";

import { useState } from "react";
import { useFamilyActions } from "@/lib/hooks/useFamilies";
import { useFamilyUiStore } from "@/store/familyUiStore";
import { formatCedis } from "@/lib/formatCedis";
import { DialogShell } from "./DialogShell";

export function FamilyRateDialog() {
  const { activeFamily, closeDialog } = useFamilyUiStore();
  const { recommendRate, approveRate, rejectRate } = useFamilyActions();
  const [amount, setAmount] = useState("");

  if (!activeFamily) return null;

  const hasRecommendation = Boolean(activeFamily.recommended_family_rate);
  const hasStanding = Boolean(activeFamily.standing_family_rate);

  return (
    <DialogShell
      title={`Own-family rate — ${activeFamily.name}`}
      description="This is what a member of this family pays when the funeral is for their own family. Everyone outside the family pays the community's general rate instead."
    >
      <div className="space-y-4 text-sm">
        <div className="rounded-sm bg-white p-3">
          <p className="text-[var(--ink-soft)]">Currently in effect</p>
          <p className="font-mono text-lg font-medium">
            {hasStanding ? formatCedis(activeFamily.standing_family_rate!) : "Not set yet"}
          </p>
        </div>

        {hasRecommendation && (
          <div className="rounded-sm bg-[var(--gold-soft)] p-3">
            <p className="text-[var(--gold)]">
              Family Head recommended {formatCedis(activeFamily.recommended_family_rate!)} — awaiting your approval.
            </p>
            <div className="mt-2 flex gap-2">
              <button
                onClick={() => approveRate.mutate({ id: activeFamily.id })}
                disabled={approveRate.isPending}
                className="rounded-sm bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
              >
                Approve as recommended
              </button>
              <button
                onClick={() => rejectRate.mutate({ id: activeFamily.id })}
                disabled={rejectRate.isPending}
                className="rounded-sm border border-[var(--clay-red)] px-3 py-1.5 text-xs font-medium text-[var(--clay-red)]"
              >
                Reject
              </button>
            </div>
          </div>
        )}

        <div>
          <label className="text-sm font-medium">
            {hasStanding || hasRecommendation ? "Set a new rate directly" : "Set the rate now"}
          </label>
          <div className="mt-1 flex gap-2">
            <input
              type="number"
              min="0.01"
              step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="e.g. 50.00"
              className="flex-1 rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
            <button
              onClick={() => amount && approveRate.mutate({ id: activeFamily.id, amount })}
              disabled={!amount || approveRate.isPending}
              className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              Set & approve
            </button>
          </div>
          <p className="mt-1 text-xs text-[var(--ink-soft)]">
            A Community Administrator can set this directly. A Family Head can only recommend
            an amount for your approval, shown above once submitted.
          </p>
        </div>

        {(approveRate.isError || rejectRate.isError) && (
          <p className="text-sm text-[var(--clay-red)]">Couldn&apos;t update the rate. Please try again.</p>
        )}
      </div>

      <div className="mt-4 flex justify-end">
        <button onClick={closeDialog} className="px-3 py-2 text-sm text-[var(--ink-soft)]">
          Close
        </button>
      </div>
    </DialogShell>
  );
}
