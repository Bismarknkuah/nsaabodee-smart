"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { dashboardApi } from "@/lib/api/dashboard";
import { formatCedis } from "@/lib/formatCedis";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";

interface BereavedFuneral {
  funeral_id: string;
  deceased_name: string;
  overview: { contributions_collected: string; gift_cash_collected: string; total_expenses: string; net_cash_position: string };
  expected_total: string;
  collected_total: string;
  collection_progress_pct: number;
  outstanding_count: number;
}
interface FamilySummary {
  active_funeral_count: number;
  total_expected: string;
  total_collected: string;
  member_compliance: { member_id: string; member_name: string; defaulter_tier: string; paid_count: number; outstanding_count: number; total_owed: string }[];
}

/**
 * 'The Deceased Rep is supposed to have analytics views of the funeral
 * activities.' Genuinely more depth than before — collection progress,
 * a full contributions/gifts/expenses breakdown, and family member
 * compliance — but still the quietest page in the app: a formal
 * statement, not a colorful dashboard. No KPI tiles, no bright accent
 * colors, no charts; a plain progress rule and plain numbers, the way
 * a real financial statement reads.
 */
export default function BereavedDashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const funerals = (data?.sections.bereaved_funerals as BereavedFuneral[] | undefined) ?? [];
  const familySummary = data?.sections.family_summary as FamilySummary | undefined;

  return (
    <DashboardPageShell folio="Folio VIII" register="Bereavement Statement" title="Your Family's Funeral" subtitle="A plain account of where things stand, for the family you represent.">
      {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
      {data && (
        <div className="lg:col-span-2 mx-auto w-full max-w-2xl border border-[var(--rule)] bg-white p-8">
          {funerals.length === 0 ? (
            <p className="text-center text-sm text-[var(--ink-soft)]">There is no active funeral for your family right now.</p>
          ) : (
            <>
              {familySummary && familySummary.active_funeral_count > 1 && (
                <div className="mb-6 border-b-2 border-[var(--ink)] pb-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--ink-soft)]">Across {familySummary.active_funeral_count} active funerals</p>
                  <p className="mt-1 text-sm">
                    {formatCedis(familySummary.total_collected)} collected of {formatCedis(familySummary.total_expected)} expected, in total.
                  </p>
                </div>
              )}

              <div className="divide-y divide-[var(--rule)]">
                {funerals.map((f) => (
                  <div key={f.funeral_id} className="py-6 first:pt-0 last:pb-0">
                    <p className="font-display text-xl">
                      <Link href={`/funerals/${f.funeral_id}`} className="hover:text-[var(--forest)] hover:underline">
                        {f.deceased_name}
                      </Link>
                    </p>

                    <div className="mt-3">
                      <div className="flex items-baseline justify-between text-sm">
                        <span className="text-[var(--ink-soft)]">Collected</span>
                        <span>{formatCedis(f.collected_total)} of {formatCedis(f.expected_total)} ({f.collection_progress_pct}%)</span>
                      </div>
                      <div className="mt-1 h-1 w-full bg-[var(--rule)]">
                        <div className="h-1 bg-[var(--ink)]" style={{ width: `${Math.min(f.collection_progress_pct, 100)}%` }} />
                      </div>
                      {f.outstanding_count > 0 && (
                        <p className="mt-1 text-xs text-[var(--ink-soft)]">{f.outstanding_count} member(s) still owing.</p>
                      )}
                    </div>

                    <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm sm:grid-cols-4">
                      <div>
                        <dt className="text-xs text-[var(--ink-soft)]">Contributions</dt>
                        <dd className="font-mono">{formatCedis(f.overview.contributions_collected)}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-[var(--ink-soft)]">Gift cash</dt>
                        <dd className="font-mono">{formatCedis(f.overview.gift_cash_collected)}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-[var(--ink-soft)]">Expenses</dt>
                        <dd className="font-mono">{formatCedis(f.overview.total_expenses)}</dd>
                      </div>
                      <div>
                        <dt className="text-xs text-[var(--ink-soft)]">Net position</dt>
                        <dd className="font-mono">{formatCedis(f.overview.net_cash_position)}</dd>
                      </div>
                    </dl>
                  </div>
                ))}
              </div>

              {familySummary && familySummary.member_compliance.length > 0 && (
                <div className="mt-6 border-t-2 border-[var(--ink)] pt-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--ink-soft)]">Your own family, member by member</p>
                  <table className="mt-3 w-full border-collapse text-sm">
                    <tbody>
                      {familySummary.member_compliance.map((m) => (
                        <tr key={m.member_id} className="border-b border-[var(--rule)] last:border-0">
                          <td className="py-1.5">
                            {m.member_name}
                            {m.defaulter_tier !== "none" && (
                              <span className="ml-2 rounded-full bg-[var(--clay-red)]/10 px-2 py-0.5 text-[10px] font-medium uppercase text-[var(--clay-red)]">
                                {m.defaulter_tier}
                              </span>
                            )}
                          </td>
                          <td className="py-1.5 text-right font-mono text-xs text-[var(--ink-soft)]">
                            {m.outstanding_count > 0 ? `${formatCedis(m.total_owed)} owing` : "settled"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </DashboardPageShell>
  );
}

