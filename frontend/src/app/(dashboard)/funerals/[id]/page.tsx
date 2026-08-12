"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useParams } from "next/navigation";
import { useFuneral, useFuneralObligations, useFuneralActions } from "@/lib/hooks/useFunerals";
import { formatCedis } from "@/lib/formatCedis";
import { ObligationTable, ObligationFilters } from "@/components/funerals/ObligationTable";
import { GiftLedgerPanel } from "@/components/funerals/GiftLedgerPanel";
import { ExpensePanel } from "@/components/funerals/ExpensePanel";
import { AttendancePanel } from "@/components/funerals/AttendancePanel";
import { FinancialOverviewStrip } from "@/components/funerals/FinancialOverviewStrip";
import { LiveUpdateBanner } from "@/components/funerals/LiveUpdateBanner";
import { PredictedCollectionsCard } from "@/components/funerals/PredictedCollectionsCard";
import { FourLedgerBreakdownCard } from "@/components/funerals/FourLedgerBreakdownCard";
import { FuneralDailyBreakdownCard } from "@/components/funerals/FuneralDailyBreakdownCard";
import { DeskAssignmentsPanel } from "@/components/funerals/DeskAssignmentsPanel";
import { MemorialPageManager } from "@/components/funerals/MemorialPageManager";
import { QrCodePanel } from "@/components/funerals/QrCodePanel";
import { CommitteePositionsPanel } from "@/components/funerals/CommitteePositionsPanel";
import { useFuneralLiveUpdates } from "@/lib/hooks/useFuneralLiveUpdates";
import type { PaymentStatus, RateType } from "@/types/funeral";

export default function FuneralDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: funeral } = useFuneral(id);
  const { close } = useFuneralActions(id);

  const [rateType, setRateType] = useState<RateType | undefined>(undefined);
  const [paymentStatus, setPaymentStatus] = useState<PaymentStatus | undefined>(undefined);
  const { data: obligations, isLoading } = useFuneralObligations(id, { rate_type: rateType, payment_status: paymentStatus });
  const { connected, lastEvent } = useFuneralLiveUpdates(id);

  if (!funeral) return null;

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
          {funeral.status === "active" ? "Currently collecting" : funeral.status}
        </p>
        <div className="mt-2">
          <LiveUpdateBanner connected={connected} lastEvent={lastEvent} />
        </div>
        <div className="mt-1 flex items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-4xl">{funeral.deceased_name}</h1>
            <p className="mt-1 text-sm text-[var(--ink-soft)]">
              {funeral.deceased_family_name} family &middot; died{" "}
              {new Date(funeral.date_of_death).toLocaleDateString()} &middot; collecting since{" "}
              {new Date(funeral.collection_start_date).toLocaleDateString()}
            </p>
          </div>
          {funeral.status === "active" && (
            <button
              onClick={() => close.mutate()}
              className="rounded-sm border border-[var(--rule)] px-4 py-2 text-sm font-medium hover:border-[var(--ink)]"
            >
              Close collection
            </button>
          )}
        </div>

        <div className="mt-4 flex flex-wrap gap-4 rounded-sm bg-[var(--surface)] p-4 text-sm">
          <RateChip label={`${funeral.deceased_family_name} family rate`} amount={funeral.own_family_amount} accent="forest" />
          <RateChip label="General rate — male" amount={funeral.general_male_amount} accent="gold" />
          <RateChip label="General rate — female" amount={funeral.general_female_amount} accent="gold" />
        </div>
      </header>

      <main className="px-8 pb-16">
        <FourLedgerBreakdownCard funeralId={id} />
        <FuneralDailyBreakdownCard funeralId={id} />

        <div className="my-4">
          <PredictedCollectionsCard funeralId={id} />
        </div>

        <div className="mb-4 rounded-sm border border-[var(--rule)] bg-white p-4">
          <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Funeral Desk</p>
          <DeskAssignmentsPanel funeralId={id} />
          <MemorialPageManager funeralId={id} />
          <QrCodePanel funeralId={id} />
          <CommitteePositionsPanel funeralId={id} />
        </div>

        <h2 className="font-display mt-4 text-xl">Ledger</h2>
        <ObligationFilters
          rateType={rateType}
          onRateType={setRateType}
          paymentStatus={paymentStatus}
          onPaymentStatus={setPaymentStatus}
        />
        <ObligationTable funeralId={id} obligations={obligations} isLoading={isLoading} />

        <GiftLedgerPanel funeralId={id} />

        <FinancialOverviewStrip funeralId={id} />
        <ExpensePanel funeralId={id} />
        <AttendancePanel funeralId={id} />
      </main>
    </div>
  );
}

function RateChip({ label, amount, accent }: { label: string; amount: string; accent: "forest" | "gold" }) {
  const tint = accent === "forest" ? "var(--forest)" : "var(--gold)";
  return (
    <div className="flex items-center gap-2">
      <span aria-hidden className="h-2 w-2 rounded-full" style={{ backgroundColor: tint }} />
      <span className="text-[var(--ink-soft)]">{label}:</span>
      <span className="font-mono font-medium">{formatCedis(amount)}</span>
    </div>
  );
}
