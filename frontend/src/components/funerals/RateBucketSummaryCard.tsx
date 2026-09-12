import { formatCedis } from "@/lib/formatCedis";
import type { RateBucketSummary } from "@/types/funeral";

export function RateBucketSummaryCard({
  label,
  rateDescription,
  summary,
  accent,
}: {
  label: string;
  rateDescription: string;
  summary: RateBucketSummary;
  accent: "forest" | "gold";
}) {
  const pct =
    Number(summary.expected_total) > 0
      ? Math.round((Number(summary.collected_total) / Number(summary.expected_total)) * 100)
      : 0;

  const tint = accent === "forest" ? "var(--forest)" : "var(--gold)";
  const tintSoft = accent === "forest" ? "var(--forest-soft)" : "var(--gold-soft)";

  return (
    <div className="rounded-sm border border-[var(--rule)] bg-white p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-lg" style={{ color: tint }}>
          {label}
        </h3>
        <span
          className="rounded-full px-2 py-0.5 text-xs font-medium"
          style={{ backgroundColor: tintSoft, color: tint }}
        >
          {summary.member_count} member{summary.member_count === 1 ? "" : "s"}
        </span>
      </div>
      <p className="mt-1 text-xs text-[var(--ink-soft)]">{rateDescription}</p>

      <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-[var(--surface)]">
        <div className="h-full" style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: tint }} />
      </div>
      <p className="mt-1 font-mono text-xs text-[var(--ink-soft)]">
        {formatCedis(summary.collected_total)} of {formatCedis(summary.expected_total)} collected ({pct}%)
      </p>

      <dl className="mt-4 grid grid-cols-3 gap-2 text-center text-xs">
        <div>
          <dt className="text-[var(--ink-soft)]">Paid</dt>
          <dd className="font-mono text-sm font-medium">{summary.fully_paid_count}</dd>
        </div>
        <div>
          <dt className="text-[var(--ink-soft)]">Partial</dt>
          <dd className="font-mono text-sm font-medium">{summary.partial_count}</dd>
        </div>
        <div>
          <dt className="text-[var(--ink-soft)]">Unpaid</dt>
          <dd className="font-mono text-sm font-medium">{summary.unpaid_count}</dd>
        </div>
      </dl>
    </div>
  );
}
