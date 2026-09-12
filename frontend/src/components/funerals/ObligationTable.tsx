"use client";

import { useState } from "react";
import type { ContributionObligation, PaymentStatus, RateType } from "@/types/funeral";
import { formatCedis } from "@/lib/formatCedis";
import { RecordPaymentDialog } from "./RecordPaymentDialog";
import { PayViaMomoDialog } from "./PayViaMomoDialog";
import { useAuthStore } from "@/store/authStore";

// 'None of the executive dashboard should have access to receive
// gifts and collector access in their dashboard.' The backend already
// correctly restricts who can actually record someone else's payment
// (PAYMENT_COLLECTING_ROLES is Collector-only, plus whoever is a real,
// specific desk assignment for this exact funeral) — but this button
// was showing to literally everyone regardless, meaning Chairman,
// Secretary, Treasurer, Financial Secretary, and Auditor would always
// hit a 403 if they actually clicked it. Community Admin and Family
// Officers are kept here since they can legitimately hold a real desk
// assignment for a specific funeral; the broad community-wide
// oversight roles never do.
const CAN_RECORD_PAYMENTS_ROLES = ["community_admin", "collector", "family_head", "family_secretary", "family_treasurer"];

const STATUS_STYLE: Record<PaymentStatus, string> = {
  paid: "bg-[var(--forest-soft)] text-[var(--forest)]",
  partial: "bg-[var(--gold-soft)] text-[var(--gold)]",
  unpaid: "bg-[var(--clay-red-soft)] text-[var(--clay-red)]",
};

export function ObligationTable({
  funeralId,
  obligations,
  isLoading,
}: {
  funeralId: string;
  obligations: ContributionObligation[] | undefined;
  isLoading: boolean;
}) {
  const [payFor, setPayFor] = useState<ContributionObligation | null>(null);
  const [momoFor, setMomoFor] = useState<ContributionObligation | null>(null);
  const user = useAuthStore((s) => s.user);
  const own_member_id = user?.linked_member_id;
  const canRecordForOthers = Boolean(user?.is_superuser || (user?.role && CAN_RECORD_PAYMENTS_ROLES.includes(user.role)));

  return (
    <div className="overflow-hidden rounded-sm border border-[var(--rule)] bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--rule)] text-left text-xs uppercase tracking-wide text-[var(--ink-soft)]">
            <th className="px-4 py-3">Member</th>
            <th className="px-4 py-3">Paying as</th>
            <th className="px-4 py-3 text-right">Owed</th>
            <th className="px-4 py-3 text-right">Paid</th>
            <th className="px-4 py-3 text-right">Balance</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody>
          {isLoading && (
            <tr>
              <td colSpan={7} className="px-4 py-6 text-center text-[var(--ink-soft)]">
                Loading ledger…
              </td>
            </tr>
          )}
          {!isLoading && obligations?.length === 0 && (
            <tr>
              <td colSpan={7} className="px-4 py-6 text-center text-[var(--ink-soft)]">
                No members match this filter.
              </td>
            </tr>
          )}
          {obligations?.map((o) => (
            <tr key={o.id} className="border-b border-[var(--rule)] last:border-b-0">
              <td className="px-4 py-3 font-medium">{o.member.full_name}</td>
              <td className="px-4 py-3 text-[var(--ink-soft)]">
                {o.rate_type === "own_family" ? "Own family" : "General"}
              </td>
              <td className="px-4 py-3 text-right font-mono">{formatCedis(o.expected_amount)}</td>
              <td className="px-4 py-3 text-right font-mono">{formatCedis(o.amount_paid)}</td>
              <td className="px-4 py-3 text-right font-mono">{formatCedis(o.balance)}</td>
              <td className="px-4 py-3">
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLE[o.payment_status]}`}>
                  {o.payment_status}
                </span>
              </td>
              <td className="px-4 py-3 text-right">
                {o.payment_status !== "paid" && (canRecordForOthers || o.member.id === own_member_id) && (
                  <div className="flex justify-end gap-2">
                    <button
                      onClick={() => setMomoFor(o)}
                      className="rounded-sm px-3 py-1 text-xs font-medium text-white"
                      style={{ backgroundColor: "var(--gold)" }}
                    >
                      Pay via MoMo
                    </button>
                    <button
                      onClick={() => setPayFor(o)}
                      className="rounded-sm border border-[var(--rule)] px-3 py-1 text-xs font-medium hover:border-[var(--forest)] hover:text-[var(--forest)]"
                    >
                      Record payment
                    </button>
                  </div>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {payFor && (
        <RecordPaymentDialog funeralId={funeralId} obligation={payFor} onClose={() => setPayFor(null)} />
      )}
      {momoFor && (
        <PayViaMomoDialog
          obligationId={momoFor.id}
          balance={momoFor.balance}
          label={momoFor.member.full_name}
          onClose={() => setMomoFor(null)}
        />
      )}
    </div>
  );
}

export function ObligationFilters({
  rateType,
  onRateType,
  paymentStatus,
  onPaymentStatus,
}: {
  rateType: RateType | undefined;
  onRateType: (v: RateType | undefined) => void;
  paymentStatus: PaymentStatus | undefined;
  onPaymentStatus: (v: PaymentStatus | undefined) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-4 py-4">
      <div className="flex gap-1 rounded-full bg-[var(--surface)] p-1 text-xs">
        {[
          { label: "All members", value: undefined },
          { label: "Own family", value: "own_family" as const },
          { label: "General", value: "general" as const },
        ].map((opt) => (
          <button
            key={opt.label}
            onClick={() => onRateType(opt.value)}
            className={`rounded-full px-3 py-1.5 font-medium ${
              rateType === opt.value ? "bg-[var(--ink)] text-white" : "text-[var(--ink-soft)]"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
      <div className="flex gap-1 rounded-full bg-[var(--surface)] p-1 text-xs">
        {[
          { label: "Any status", value: undefined },
          { label: "Unpaid", value: "unpaid" as const },
          { label: "Partial", value: "partial" as const },
          { label: "Paid", value: "paid" as const },
        ].map((opt) => (
          <button
            key={opt.label}
            onClick={() => onPaymentStatus(opt.value)}
            className={`rounded-full px-3 py-1.5 font-medium ${
              paymentStatus === opt.value ? "bg-[var(--ink)] text-white" : "text-[var(--ink-soft)]"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  );
}
