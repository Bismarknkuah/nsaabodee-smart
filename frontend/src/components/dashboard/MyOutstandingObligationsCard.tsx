"use client";

import { useState } from "react";
import { useMyOutstandingObligations } from "@/lib/hooks/useReports";
import { PayViaMomoDialog } from "@/components/funerals/PayViaMomoDialog";
import { formatCedis } from "@/lib/formatCedis";
import type { OutstandingObligation } from "@/types/reports";

/**
 * "Add MoMo pay prompts for members to pay their contributions... very
 * easy." This is that prompt — every currently-active funeral a member
 * owes something toward, each with its own one-tap "Pay via MoMo"
 * button, right on their own dashboard. No need to find a collector,
 * no need to know your own obligation ID.
 */
export function MyOutstandingObligationsCard() {
  const { data, isLoading } = useMyOutstandingObligations();
  const [payFor, setPayFor] = useState<OutstandingObligation | null>(null);

  if (isLoading || !data || data.length === 0) return null;

  return (
    <section className="rounded-sm border-2 border-[var(--gold)] bg-white p-5">
      <h2 className="font-display text-lg" style={{ color: "var(--gold)" }}>
        You have contributions due
      </h2>
      <ul className="mt-3 divide-y divide-[var(--rule)]">
        {data.map((o) => (
          <li key={o.obligation_id} className="flex items-center justify-between py-3">
            <div>
              <p className="text-sm font-medium">{o.deceased_name}</p>
              <p className="text-xs text-[var(--ink-soft)]">
                {o.rate_type === "own_family" ? "Family Ledger" : "Community Ledger"} · owe {formatCedis(o.balance)}
              </p>
            </div>
            <button
              onClick={() => setPayFor(o)}
              className="rounded-sm px-4 py-2 text-sm font-medium text-white"
              style={{ backgroundColor: "var(--gold)" }}
            >
              Pay via MoMo
            </button>
          </li>
        ))}
      </ul>

      {payFor && (
        <PayViaMomoDialog
          obligationId={payFor.obligation_id}
          balance={payFor.balance}
          label={payFor.deceased_name}
          onClose={() => setPayFor(null)}
        />
      )}
    </section>
  );
}
