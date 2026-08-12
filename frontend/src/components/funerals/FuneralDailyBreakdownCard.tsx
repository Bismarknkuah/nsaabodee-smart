"use client";

import { useQuery } from "@tanstack/react-query";
import { reportsApi } from "@/lib/api/reports";
import { formatCedis } from "@/lib/formatCedis";

/**
 * "It starts Friday and closes Sunday evening but they should be able
 * to know the amount they received each day." A quiet day genuinely
 * shows GH₵0, not a gap — that's the point of showing every day in the
 * window rather than only the days something happened.
 */
export function FuneralDailyBreakdownCard({ funeralId }: { funeralId: string }) {
  const { data, isError } = useQuery({
    queryKey: ["funeral-daily-breakdown", funeralId],
    queryFn: () => reportsApi.funeralDailyBreakdown(funeralId),
    enabled: Boolean(funeralId),
    retry: false,
  });

  if (isError || !data) return null;

  return (
    <div className="mt-4 rounded-sm border border-[var(--rule)] bg-white p-4">
      <p className="font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-[var(--ink-soft)]">Day by day</p>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--rule)] text-left text-xs uppercase tracking-wide text-[var(--ink-soft)]">
              <th className="py-1.5 pr-4">Date</th>
              <th className="py-1.5 pr-4 text-right">Contributions</th>
              {data.days[0] && "gifts_total" in data.days[0] && <th className="py-1.5 pr-4 text-right">Gifts</th>}
              <th className="py-1.5 text-right">Total</th>
            </tr>
          </thead>
          <tbody>
            {data.days.map((d) => (
              <tr key={d.date} className="border-b border-[var(--rule)] last:border-b-0">
                <td className="py-1.5 pr-4">{new Date(d.date).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}</td>
                <td className="py-1.5 pr-4 text-right font-mono">{formatCedis(d.contributions_total)}</td>
                {d.gifts_total !== undefined && <td className="py-1.5 pr-4 text-right font-mono">{formatCedis(d.gifts_total)}</td>}
                <td className="py-1.5 text-right font-mono font-medium">{formatCedis(d.combined_total)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-right text-sm font-medium">Total so far: {formatCedis(data.grand_total)}</p>
    </div>
  );
}
