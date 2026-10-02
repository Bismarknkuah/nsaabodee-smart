"use client";

import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

/**
 * Split out from DashboardVisuals.tsx on purpose: recharts is a real
 * dependency weight, and several pages (KPI tiles, folio panels, no
 * chart at all) were pulling in the whole charting library just by
 * importing anything from the same module. Only pages that actually
 * render a trend now pay for it.
 *
 * ResponsiveContainer measures its parent's actual pixel size to size
 * the chart — a well-documented class of recharts issue is measuring
 * before that parent has settled into its real layout (during
 * server-rendered first paint, or the instant a CSS grid column is
 * still computing its width), which can throw rather than just look
 * wrong. Rendering the chart only after the component has mounted
 * client-side, plus explicit minimum dimensions as a second
 * safeguard, is the standard fix for exactly this.
 */
export function TrendChart({ data, label = "Collected" }: { data: { date: string; total: string }[]; label?: string }) {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const chartData = data.map((d) => ({
    day: new Date(d.date).toLocaleDateString(undefined, { weekday: "short" }),
    amount: Number(d.total) || 0,
  }));

  return (
    <div className="mt-5">
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--ink-soft)]">{label} — last 7 days</p>
      <div className="mt-2 h-40 w-full">
        {mounted && (
          <ResponsiveContainer width="100%" height="100%" minWidth={200} minHeight={100}>
            <BarChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="2 3" vertical={false} stroke="var(--rule)" />
              <XAxis dataKey="day" tick={{ fontSize: 11, fill: "var(--ink-soft)", fontFamily: "var(--font-plex-mono)" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "var(--ink-soft)", fontFamily: "var(--font-plex-mono)" }} axisLine={false} tickLine={false} width={40} />
              <Tooltip
                formatter={(value: number) => [`GHS ${value.toFixed(2)}`, label]}
                contentStyle={{ fontSize: 12, borderRadius: 2, border: "1px solid var(--rule)", fontFamily: "var(--font-inter)" }}
              />
              <Bar dataKey="amount" fill="var(--forest)" radius={[2, 2, 0, 0]} maxBarSize={28} />
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
