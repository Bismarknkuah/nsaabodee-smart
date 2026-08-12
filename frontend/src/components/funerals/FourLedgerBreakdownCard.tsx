"use client";

import { useQuery } from "@tanstack/react-query";
import { reportsApi } from "@/lib/api/reports";
import { formatCedis } from "@/lib/formatCedis";

/**
 * "Every member name should be in two ledgers, the family ledger and
 * the community ledger" — plus the two donation ledgers this pass adds.
 * Guest/Town Leaders figures are simply absent from the response for
 * most committee roles (see the backend's FuneralLedgerBreakdownView) —
 * this renders whatever it actually gets back rather than assuming
 * every viewer sees every ledger.
 */
export function FourLedgerBreakdownCard({ funeralId }: { funeralId: string }) {
  const { data } = useQuery({
    queryKey: ["funeral-ledger-breakdown", funeralId],
    queryFn: () => reportsApi.funeralLedgerBreakdown(funeralId),
    enabled: Boolean(funeralId),
  });

  if (!data) return null;

  return (
    <div className="my-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <LedgerTile
        label="Family Ledger"
        sublabel={`${data.deceased_family_name} family, own-family rate`}
        accent="forest"
        stat={`${data.family_ledger.member_count} members`}
        value={formatCedis(data.family_ledger.collected_total)}
        total={formatCedis(data.family_ledger.expected_total)}
      />
      <LedgerTile
        label="Community Ledger"
        sublabel="Everyone else, general rate"
        accent="gold"
        stat={`${data.community_ledger.member_count} members`}
        value={formatCedis(data.community_ledger.collected_total)}
        total={formatCedis(data.community_ledger.expected_total)}
      />
      {data.guest_ledger ? (
        <LedgerTile
          label="Guest Ledger"
          sublabel="Visiting well-wishers"
          accent="violet"
          stat={`${data.guest_ledger.donor_count} donors`}
          value={formatCedis(data.guest_ledger.total_value)}
        />
      ) : (
        <RestrictedTile label="Guest Ledger" />
      )}
      {data.town_leaders_ledger ? (
        <LedgerTile
          label="Town Leaders Ledger"
          sublabel="King & Elders"
          accent="violet"
          stat={`${data.town_leaders_ledger.donor_count} donors`}
          value={formatCedis(data.town_leaders_ledger.total_value)}
        />
      ) : (
        <RestrictedTile label="Town Leaders Ledger" />
      )}
    </div>
  );
}

function LedgerTile({
  label, sublabel, accent, stat, value, total,
}: {
  label: string; sublabel: string; accent: "forest" | "gold" | "violet"; stat: string; value: string; total?: string;
}) {
  const color = { forest: "var(--forest)", gold: "var(--gold)", violet: "var(--violet)" }[accent];
  return (
    <div className="rounded-sm border border-[var(--rule)] bg-white p-4">
      <p className="font-mono text-[11px] font-medium uppercase tracking-[0.16em]" style={{ color }}>{label}</p>
      <p className="mt-1 text-xs text-[var(--ink-soft)]">{sublabel}</p>
      <p className="mt-2 font-mono text-xl font-semibold">{value}</p>
      {total && <p className="text-xs text-[var(--ink-soft)]">of {total} expected</p>}
      <p className="mt-1 text-xs text-[var(--ink-soft)]">{stat}</p>
    </div>
  );
}

function RestrictedTile({ label }: { label: string }) {
  return (
    <div className="rounded-sm border border-dashed border-[var(--rule)] bg-[var(--paper)] p-4">
      <p className="font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-[var(--ink-soft)]">{label}</p>
      <p className="mt-2 text-xs text-[var(--ink-soft)]">
        Only this family&apos;s head or a community administrator can see this.
      </p>
    </div>
  );
}
