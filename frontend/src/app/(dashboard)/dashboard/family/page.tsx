"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api/dashboard";
import { formatCedis } from "@/lib/formatCedis";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";
import { KpiTile, SectionCard, FolioLink } from "@/components/dashboard/DashboardVisuals";
import { IconMoney, IconPeople, IconFuneral } from "@/components/icons/DashboardIcons";
import { useAuthStore } from "@/store/authStore";
import { usePendingDonationAccounts, useApproveDonationAccount } from "@/lib/hooks/useGifts";

interface FamilyOverview {
  family_name?: string;
  message?: string;
  statement?: {
    member_count: number;
    as_deceaseds_family: { expected_total: string; collected_total: string; obligation_count: number };
    donation_receivers: { member_name: string; donation_count: number; total_received: string }[];
  };
  member_compliance?: { member_id: string; member_name: string; defaulter_tier: string; paid_count: number; outstanding_count: number; total_owed: string }[];
  upcoming_meetings?: { id: string; title: string; scheduled_for: string; location: string; family_id: string | null }[];
}
interface FamilyFundOfficerEntry {
  family_id: string;
  family_name: string;
  your_role: "head" | "secretary" | "treasurer";
  funds: { fund_id: string; fund_name: string; total_collected: string; contributor_count: number }[];
}

/** The family's own name reads like a chapter heading; the Family Fund gets a dashed border and its own italic note, marking it as a genuinely separate, private ledger rather than another section of the same book. */
export default function FamilyDashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const overview = data?.sections.family_overview as FamilyOverview | undefined;
  const fundEntries = data?.sections.family_fund_overview as FamilyFundOfficerEntry[] | undefined;
  const currentUser = useAuthStore((s) => s.user);
  const isFamilyHead = currentUser?.role === "family_head";
  const { data: pendingDonationAccounts } = usePendingDonationAccounts(isFamilyHead);
  const approveDonationAccount = useApproveDonationAccount();

  return (
    <DashboardPageShell folio="Folio V" register="Family Register" title="Your Family's Affairs" subtitle="Family Head, Family Secretary, and Family Treasurer.">
      {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}

      {overview && (
        <>
          {overview.message && <p className="lg:col-span-2 text-sm text-[var(--ink-soft)]">{overview.message}</p>}
          {overview.family_name && (
            <>
              <div className="lg:col-span-2 border-b-2 border-[var(--ink)] pb-3">
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--ink-soft)]">The house of</p>
                <h2 className="font-display text-3xl">{overview.family_name}</h2>
              </div>

              {overview.statement && (
                <>
                  <div className="lg:col-span-2 grid grid-cols-2 gap-px border border-[var(--rule)] bg-[var(--rule)] sm:grid-cols-4">
                    <KpiTile label="Members" value={overview.statement.member_count} color="violet" icon={<IconPeople />} />
                    <KpiTile label="Own obligations" value={overview.statement.as_deceaseds_family.obligation_count} color="gold" icon={<IconFuneral />} />
                    <KpiTile label="Expected" value={formatCedis(overview.statement.as_deceaseds_family.expected_total)} color="gold" icon={<IconMoney />} />
                    <KpiTile label="Collected" value={formatCedis(overview.statement.as_deceaseds_family.collected_total)} color="forest" icon={<IconMoney />} />
                  </div>

                  <div className="lg:col-span-2 flex flex-wrap gap-3 border border-dashed border-[var(--rule)] bg-[var(--surface)] p-4">
                    <FolioLink href="/members">Manage members</FolioLink>
                    {isFamilyHead && <FolioLink href="/tasks">Assign a task</FolioLink>}
                    <FolioLink href="/funerals">Funeral desks</FolioLink>
                  </div>

                  {overview.statement.donation_receivers.length > 0 && (
                    <SectionCard title="Donations received" eyebrow="By who it was given to" accent="violet">
                      <table className="w-full border-collapse text-sm">
                        <tbody>
                          {overview.statement.donation_receivers.map((r) => (
                            <tr key={r.member_name} className="border-b border-[var(--rule)] last:border-0">
                              <td className="py-2">{r.member_name}</td>
                              <td className="py-2 text-right font-mono text-xs text-[var(--ink-soft)]">{r.donation_count}×</td>
                              <td className="py-2 text-right font-display">{formatCedis(r.total_received)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </SectionCard>
                  )}

                  {overview.member_compliance && overview.member_compliance.length > 0 && (
                    <SectionCard title="Member compliance" eyebrow="Who's paid, who's still owing" accent="gold">
                      <table className="w-full border-collapse text-sm">
                        <thead>
                          <tr className="border-b border-[var(--rule)] text-left text-xs uppercase text-[var(--ink-soft)]">
                            <th className="pb-1 font-medium">Member</th>
                            <th className="pb-1 text-right font-medium">Paid</th>
                            <th className="pb-1 text-right font-medium">Outstanding</th>
                            <th className="pb-1 text-right font-medium">Owed</th>
                          </tr>
                        </thead>
                        <tbody>
                          {overview.member_compliance.map((m) => (
                            <tr key={m.member_id} className="border-b border-[var(--rule)] last:border-0">
                              <td className="py-2">
                                {m.member_name}
                                {m.defaulter_tier !== "none" && (
                                  <span className="ml-2 rounded-full bg-[var(--clay-red)]/10 px-2 py-0.5 text-[10px] font-medium uppercase text-[var(--clay-red)]">
                                    {m.defaulter_tier}
                                  </span>
                                )}
                              </td>
                              <td className="py-2 text-right font-mono text-xs">{m.paid_count}</td>
                              <td className="py-2 text-right font-mono text-xs">{m.outstanding_count}</td>
                              <td className="py-2 text-right font-display">{Number(m.total_owed) > 0 ? formatCedis(m.total_owed) : "—"}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </SectionCard>
                  )}

                  {overview.upcoming_meetings && overview.upcoming_meetings.length > 0 && (
                    <SectionCard title="Meeting schedule" eyebrow="Community-wide and your own family's" accent="forest">
                      <ul className="space-y-3">
                        {overview.upcoming_meetings.map((m) => (
                          <li key={m.id} className="border-l-2 border-[var(--forest)] pl-3">
                            <p className="text-sm font-medium">
                              {m.title}
                              {!m.family_id && <span className="ml-2 text-xs text-[var(--ink-soft)]">(community-wide)</span>}
                            </p>
                            <p className="text-xs text-[var(--ink-soft)]">
                              {new Date(m.scheduled_for).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                              {m.location && ` · ${m.location}`}
                            </p>
                          </li>
                        ))}
                      </ul>
                    </SectionCard>
                  )}

                  {isFamilyHead && pendingDonationAccounts && pendingDonationAccounts.length > 0 && (
                    <SectionCard title="Donation account approvals" eyebrow="Activated only once you approve" accent="gold">
                      <p className="text-xs text-[var(--ink-soft)]">
                        Someone registered these family members to receive gifts on a funeral&apos;s behalf —
                        nobody can give a gift through them until you approve.
                      </p>
                      <ul className="mt-3 space-y-2">
                        {pendingDonationAccounts.map((reg) => (
                          <li key={reg.id} className="flex items-center justify-between gap-3 rounded-sm bg-white px-3 py-2">
                            <span className="text-sm">{reg.member_name}</span>
                            <button
                              onClick={() => approveDonationAccount.mutate(reg.id)}
                              disabled={approveDonationAccount.isPending}
                              className="rounded-sm border border-[var(--forest)] px-2 py-1 text-xs text-[var(--forest)] disabled:opacity-50"
                            >
                              Approve
                            </button>
                          </li>
                        ))}
                      </ul>
                    </SectionCard>
                  )}
                </>
              )}
            </>
          )}
        </>
      )}

      {fundEntries && fundEntries.length > 0 && (
        <div className="lg:col-span-2 border-2 border-dashed border-[var(--violet)] p-5">
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--violet)]">A separate, private ledger</p>
          <h2 className="font-display mt-1 text-xl">Family Fund</h2>
          <p className="mt-1 text-xs italic text-[var(--ink-soft)]">Never part of the community's own ledger — only your family sees this.</p>
          {fundEntries.map((entry) => (
            <div key={entry.family_id} className="mt-4 border-t border-[var(--rule)] pt-4">
              <div className="flex items-center justify-between">
                <p className="font-medium">{entry.family_name}</p>
                <span className="rounded-full bg-[var(--violet-soft)] px-2 py-0.5 text-xs font-medium" style={{ color: "var(--violet)" }}>
                  You&apos;re the {entry.your_role}
                </span>
              </div>
              {entry.funds.length === 0 ? (
                <p className="mt-1 text-xs text-[var(--ink-soft)]">No funds created yet.</p>
              ) : (
                <ul className="mt-1 space-y-0.5">
                  {entry.funds.map((f) => (
                    <li key={f.fund_id} className="flex justify-between text-sm">
                      <span>{f.fund_name}</span>
                      <span className="font-mono">{formatCedis(f.total_collected)} ({f.contributor_count})</span>
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-2"><FolioLink href={`/family-fund/${entry.family_id}`}>Manage this fund</FolioLink></div>
            </div>
          ))}
        </div>
      )}
    </DashboardPageShell>
  );
}
