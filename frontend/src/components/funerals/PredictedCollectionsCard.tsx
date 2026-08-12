"use client";

import { usePredictedCollections } from "@/lib/hooks/useAiFeatures";
import { formatCedis } from "@/lib/formatCedis";

export function PredictedCollectionsCard({ funeralId }: { funeralId: string }) {
  const { data } = usePredictedCollections(funeralId);
  if (!data) return null;

  return (
    <div className="rounded-sm border border-dashed border-[var(--rule)] bg-white p-4">
      <p className="font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-[var(--ink-soft)]">Prediction</p>
      {data.has_historical_data ? (
        <>
          <p className="mt-1 text-sm">
            Based on {data.based_on_funeral_count} past funeral{data.based_on_funeral_count === 1 ? "" : "s"} in
            this community, about <strong>{Math.round((data.predicted_collection_rate ?? 0) * 100)}%</strong> of
            what&apos;s expected typically comes in — projected at{" "}
            <strong>{formatCedis(data.predicted_collected_total ?? "0")}</strong> of{" "}
            {formatCedis(data.expected_total)} expected.
          </p>
          <p className="mt-1 text-xs text-[var(--ink-soft)]">
            A historical average, not a guarantee — treat it as a planning estimate.
          </p>
        </>
      ) : (
        <p className="mt-1 text-sm text-[var(--ink-soft)]">{data.note}</p>
      )}
    </div>
  );
}
