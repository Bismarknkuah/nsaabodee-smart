"use client";

import "@/styles/family-registry-tokens.css";
import Link from "next/link";
import { useDefaulters } from "@/lib/hooks/useMembers";
import { KpiTile } from "@/components/dashboard/DashboardVisuals";
import { IconWarning, IconPeople } from "@/components/icons/DashboardIcons";
import type { DefaulterTier } from "@/types/member";

const TIER_ACCENT: Record<Exclude<DefaulterTier, "none">, string> = {
  warning: "var(--gold)",
  high_warning: "var(--gold)",
  flagged: "var(--clay-red)",
};

const TIER_LABEL: Record<Exclude<DefaulterTier, "none">, string> = {
  warning: "Warning",
  high_warning: "High warning",
  flagged: "Flagged",
};

export default function DefaultersDashboardPage() {
  const { data: members, isLoading } = useDefaulters();
  const flaggedCount = members?.filter((m) => m.defaulter_tier === "flagged").length ?? 0;

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-[var(--clay-red)]">Follow-up required</p>
        <h1 className="font-display mt-1 text-4xl">Defaulters</h1>
        <p className="mt-2 max-w-xl text-sm text-[var(--ink-soft)]">
          Recalculated automatically every time a funeral&apos;s collection closes. Members
          flagged here have already had their Family Head and the Treasurer notified.
        </p>
      </header>

      <main className="px-8 py-8">
        <div className="grid grid-cols-2 gap-px border border-[var(--rule)] bg-[var(--rule)] sm:max-w-md">
          <KpiTile label="Total flagged" value={members?.length ?? 0} color="gold" icon={<IconPeople />} />
          <KpiTile label="Highest tier" value={flaggedCount} color="clay" icon={<IconWarning />} />
        </div>

        <div className="mt-6">
          {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
          {!isLoading && members?.length === 0 && (
            <div className="border border-dashed border-[var(--rule)] px-6 py-10 text-center">
              <p className="font-display text-lg">Nobody is behind right now</p>
            </div>
          )}

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {members?.map((m) => (
              <Link
                key={m.id}
                href={`/members/${m.id}`}
                className="bg-white p-4 transition-shadow hover:shadow-md"
                style={{ borderTop: `3px solid ${TIER_ACCENT[m.defaulter_tier as Exclude<DefaulterTier, "none">]}` }}
              >
                <div className="flex items-center justify-between">
                  <p className="font-display text-lg">{m.full_name}</p>
                  <span
                    className="font-mono text-[10px] font-medium uppercase tracking-wide"
                    style={{ color: TIER_ACCENT[m.defaulter_tier as Exclude<DefaulterTier, "none">] }}
                  >
                    {TIER_LABEL[m.defaulter_tier as Exclude<DefaulterTier, "none">]}
                  </span>
                </div>
                <p className="font-mono mt-1 text-xs text-[var(--ink-soft)]">
                  {m.family_detail?.name ?? "No family"} · {m.membership_number}
                </p>
                <p className="mt-2 text-sm">
                  Missed <strong>{m.missed_contributions_count}</strong> contribution
                  {m.missed_contributions_count === 1 ? "" : "s"}
                </p>
              </Link>
            ))}
          </div>
        </div>
      </main>
    </div>
  );
}
