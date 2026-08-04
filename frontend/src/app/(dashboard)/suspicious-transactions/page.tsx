"use client";

import "@/styles/family-registry-tokens.css";
import { useSuspiciousTransactions, useReviewSuspiciousTransaction } from "@/lib/hooks/useAiFeatures";
import { formatCedis } from "@/lib/formatCedis";
import { KpiTile } from "@/components/dashboard/DashboardVisuals";
import { IconWarning } from "@/components/icons/DashboardIcons";

const REASON_LABEL: Record<string, string> = {
  amount_outlier: "Unusual amount for this collector",
  rapid_succession: "Many payments in rapid succession",
};

const STATUS_ACCENT: Record<string, string> = {
  unreviewed: "var(--gold)",
  confirmed: "var(--clay-red)",
  dismissed: "var(--ink-soft)",
};

export default function SuspiciousTransactionsPage() {
  const { data, isLoading } = useSuspiciousTransactions();
  const review = useReviewSuspiciousTransaction();
  const unreviewedCount = data?.filter((f) => f.review_status === "unreviewed").length ?? 0;

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-[var(--clay-red)]">For review</p>
        <h1 className="font-display mt-1 text-4xl">Suspicious Transactions</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Two explainable rules, not a black-box score: a payment amount unusual for that
          collector&apos;s own history, or an unusual burst of payments in a short window. Both
          need a real baseline before they ever fire, and neither is proof of anything on its
          own — a busy funeral genuinely produces bursts of real payments too. Review each and
          confirm or dismiss.
        </p>
      </header>

      <main className="px-8 py-8">
        <div className="grid grid-cols-2 gap-px border border-[var(--rule)] bg-[var(--rule)] sm:max-w-md">
          <KpiTile label="Awaiting review" value={unreviewedCount} color={unreviewedCount > 0 ? "clay" : "forest"} icon={<IconWarning />} />
          <KpiTile label="Total flagged" value={data?.length ?? 0} color="gold" />
        </div>

        <div className="mt-6">
          {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
          {data?.length === 0 && (
            <div className="border border-dashed border-[var(--rule)] px-6 py-10 text-center">
              <p className="font-display text-lg">Nothing flagged right now</p>
            </div>
          )}

          <ul className="space-y-3">
            {data?.map((flag) => (
              <li key={flag.id} className="border border-[var(--rule)] bg-white p-4" style={{ borderLeft: `3px solid ${STATUS_ACCENT[flag.review_status]}` }}>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <p className="font-medium">{flag.member_name}</p>
                      <span className="font-mono text-[10px] font-medium uppercase tracking-wide" style={{ color: STATUS_ACCENT[flag.review_status] }}>
                        {flag.review_status}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-[var(--ink-soft)]">{REASON_LABEL[flag.reason]}</p>
                    <p className="mt-1 text-sm">{flag.detail}</p>
                    <p className="font-mono mt-1 text-xs text-[var(--ink-soft)]">
                      {formatCedis(flag.amount)} · flagged {new Date(flag.flagged_at).toLocaleString()}
                    </p>
                  </div>
                  {flag.review_status === "unreviewed" && (
                    <div className="flex shrink-0 gap-2">
                      <button
                        onClick={() => review.mutate({ id: flag.id, reviewStatus: "dismissed" })}
                        className="border border-[var(--rule)] px-3 py-1.5 text-xs font-medium hover:border-[var(--ink)]"
                      >
                        Dismiss
                      </button>
                      <button
                        onClick={() => review.mutate({ id: flag.id, reviewStatus: "confirmed" })}
                        className="bg-[var(--clay-red)] px-3 py-1.5 text-xs font-medium text-white"
                      >
                        Confirm concern
                      </button>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      </main>
    </div>
  );
}
