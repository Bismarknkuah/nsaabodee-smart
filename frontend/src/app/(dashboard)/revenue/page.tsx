"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery } from "@tanstack/react-query";
import { tenantsApi } from "@/lib/api/tenants";
import { formatCedis } from "@/lib/formatCedis";
import { KpiTile } from "@/components/dashboard/DashboardVisuals";
import { IconMoney, IconWarning } from "@/components/icons/DashboardIcons";

export default function RevenuePage() {
  const { data: report, isLoading, error } = useQuery({ queryKey: ["platform-revenue"], queryFn: () => tenantsApi.platformRevenue() });

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Platform Administration</p>
        <h1 className="font-display mt-1 text-4xl">Revenue</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          The platform&apos;s own subscription and rental fee income only — never a community&apos;s
          contribution or gift ledgers, which this deliberately never touches.
        </p>
      </header>

      <main className="px-8 py-8">
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
        {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
        {report && (
          <>
            <div className="grid grid-cols-2 gap-px border border-[var(--rule)] bg-[var(--rule)] sm:grid-cols-3">
              <KpiTile label={`Paid (${report.paid_count})`} value={formatCedis(report.total_paid)} color="forest" icon={<IconMoney />} />
              <KpiTile label={`Outstanding (${report.unpaid_count})`} value={formatCedis(report.total_outstanding)} color="clay" icon={<IconWarning />} />
              <KpiTile label={`Waived (${report.waived_count})`} value={formatCedis(report.total_waived)} color="gold" />
            </div>

            <div className="mt-6 border border-[var(--rule)] bg-white p-5">
              <h2 className="font-display text-xl">Paid revenue by community</h2>
              {report.by_community.length === 0 ? (
                <p className="mt-3 text-sm text-[var(--ink-soft)]">Nothing paid yet.</p>
              ) : (
                <table className="mt-3 w-full border-collapse text-sm">
                  <tbody>
                    {report.by_community.map((row) => (
                      <tr key={row.community_name} className="border-b border-[var(--rule)] last:border-0">
                        <td className="py-2">{row.community_name}</td>
                        <td className="py-2 text-right font-mono">{formatCedis(row.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
