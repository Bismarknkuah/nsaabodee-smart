"use client";

import "@/styles/family-registry-tokens.css";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api/dashboard";
import { formatCedis } from "@/lib/formatCedis";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";
import { SectionCard, FolioLink } from "@/components/dashboard/DashboardVisuals";
import { useAuthStore } from "@/store/authStore";
import { usePendingDonationAccounts, useApproveDonationAccount } from "@/lib/hooks/useGifts";
import { useDecideFuneralExpense } from "@/lib/hooks/useFamilyFunds";
import { useDecideTaskCompletion } from "@/lib/hooks/useTasks";

interface PendingExpenseApproval {
  id: string;
  item_name: string;
  seller_name: string;
  amount: string;
  date_purchased: string;
  funeral_event__deceased_name: string;
  recorded_by__username: string | null;
}
interface RecordedExpense {
  id: string;
  item_name: string;
  amount: string;
  status: "pending" | "approved" | "rejected";
  date_purchased: string;
  funeral_event__deceased_name: string;
  rejection_reason: string;
}
interface FamilyOverview {
  family_id?: string;
  family_name?: string;
  role?: string;
  message?: string;
  statement?: {
    member_count: number;
    as_deceaseds_family: { expected_total: string; collected_total: string; obligation_count: number };
    donation_receivers: { member_name: string; donation_count: number; total_received: string }[];
  };
  member_compliance?: { member_id: string; member_name: string; defaulter_tier: string; paid_count: number; outstanding_count: number; total_owed: string }[];
  upcoming_meetings?: { id: string; title: string; scheduled_for: string; location: string; family_id: string | null }[];
  my_desk_assignments?: { funeral_event_id: string; funeral_event__deceased_name: string; desk_type: string }[];
  // Family Head and Family Treasurer only — 'oversight of all family
  // activities' / 'oversight of all financial information and aspects.'
  financial_overview?: { total_fund_contributions: string; total_approved_expenses: string; total_pending_expenses: string; net_position: string };
  pending_expense_approvals?: PendingExpenseApproval[];
  // Family Treasurer only — genuinely deeper than what the Head gets.
  expenditure_summary?: { pending: { count: number; total: string }; approved: { count: number; total: string }; rejected: { count: number; total: string }; total_all_recorded: string };
  fund_summaries?: { fund_id: string; fund_name: string; is_active: boolean; contribution_count: number; contributor_count: number; total_collected: string }[];
  // 'Each treasurer should have access to data of those who have paid in his family and who haven't.'
  payment_status?: {
    paid_member_count: number; outstanding_member_count: number;
    paid_members: { member_id: string; member_name: string; total_paid: string; funeral_count: number }[];
    outstanding_members: { member_id: string; member_name: string; total_owed: string; funeral_count: number }[];
  };
  // Family Secretary only — their own record-keeping, not an approval queue.
  my_recorded_expenses?: RecordedExpense[];
  // Family Head only — genuinely new, was computed by the backend but never surfaced anywhere before.
  task_summary?: { pending: number; in_progress: number; awaiting_your_approval: number; done: number; overdue: number };
  tasks_awaiting_approval?: { id: string; title: string; assigned_to__full_name: string; due_date: string | null }[];
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
  const isFamilyTreasurer = currentUser?.role === "family_treasurer";
  const isFamilySecretary = currentUser?.role === "family_secretary";
  const { data: pendingDonationAccounts } = usePendingDonationAccounts(isFamilyHead);
  const approveDonationAccount = useApproveDonationAccount();
  const decideExpense = useDecideFuneralExpense(overview?.family_id ?? "");
  const decideTask = useDecideTaskCompletion();

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
                  <div className="lg:col-span-2 border-b border-[var(--rule)] pb-4 font-mono text-sm">
                    <span>{overview.statement.member_count} members</span>
                    {overview.statement.as_deceaseds_family.obligation_count > 0 && (
                      <>
                        <span className="mx-2 text-[var(--rule)]">·</span>
                        <span>
                          As deceased&apos;s own family: {formatCedis(overview.statement.as_deceaseds_family.collected_total)} collected of{" "}
                          {formatCedis(overview.statement.as_deceaseds_family.expected_total)} expected, across{" "}
                          {overview.statement.as_deceaseds_family.obligation_count} obligation(s)
                        </span>
                      </>
                    )}
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

                  {overview.financial_overview && (
                    <SectionCard
                      title="Financial overview"
                      eyebrow={isFamilyTreasurer ? "Every fund and expense, in full" : "The combined picture"}
                      accent="forest"
                    >
                      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                        <div>
                          <p className="text-xs text-[var(--ink-soft)]">Raised</p>
                          <p className="font-display text-lg">{formatCedis(overview.financial_overview.total_fund_contributions)}</p>
                        </div>
                        <div>
                          <p className="text-xs text-[var(--ink-soft)]">Approved spend</p>
                          <p className="font-display text-lg">{formatCedis(overview.financial_overview.total_approved_expenses)}</p>
                        </div>
                        <div>
                          <p className="text-xs text-[var(--ink-soft)]">Awaiting decision</p>
                          <p className="font-display text-lg text-[var(--gold)]">{formatCedis(overview.financial_overview.total_pending_expenses)}</p>
                        </div>
                        <div>
                          <p className="text-xs text-[var(--ink-soft)]">Net position</p>
                          <p className="font-display text-lg" style={{ color: "var(--forest)" }}>{formatCedis(overview.financial_overview.net_position)}</p>
                        </div>
                      </div>

                      {isFamilyTreasurer && overview.fund_summaries && overview.fund_summaries.length > 0 && (
                        <div className="mt-4 border-t border-[var(--rule)] pt-3">
                          <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Every fund</p>
                          <ul className="mt-2 space-y-1">
                            {overview.fund_summaries.map((f) => (
                              <li key={f.fund_id} className="flex justify-between text-sm">
                                <span>{f.fund_name}{!f.is_active && <span className="ml-1 text-xs text-[var(--ink-soft)]">(inactive)</span>}</span>
                                <span className="font-mono text-xs">{formatCedis(f.total_collected)} · {f.contributor_count} contributor(s)</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {isFamilyTreasurer && overview.expenditure_summary && (
                        <div className="mt-4 border-t border-[var(--rule)] pt-3">
                          <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Every expense, by status</p>
                          <div className="mt-2 grid grid-cols-3 gap-3 text-sm">
                            <div><span className="text-[var(--gold)]">{overview.expenditure_summary.pending.count} pending</span></div>
                            <div><span className="text-[var(--forest)]">{overview.expenditure_summary.approved.count} approved</span></div>
                            <div><span className="text-[var(--clay-red)]">{overview.expenditure_summary.rejected.count} rejected</span></div>
                          </div>
                        </div>
                      )}
                    </SectionCard>
                  )}

                  {overview.payment_status && (
                    <SectionCard
                      title="Who's paid in your family"
                      eyebrow={`${overview.payment_status.paid_member_count} paid · ${overview.payment_status.outstanding_member_count} outstanding`}
                      accent="forest"
                    >
                      <div className="grid gap-4 sm:grid-cols-2">
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Paid</p>
                          <ul className="mt-2 max-h-48 divide-y divide-[var(--rule)] overflow-y-auto">
                            {overview.payment_status.paid_members.map((m) => (
                              <li key={m.member_id} className="flex justify-between py-1.5 text-sm">
                                <span>{m.member_name}</span>
                                <span className="font-mono text-xs" style={{ color: "var(--forest)" }}>{formatCedis(m.total_paid)}</span>
                              </li>
                            ))}
                            {overview.payment_status.paid_members.length === 0 && (
                              <li className="py-1.5 text-xs text-[var(--ink-soft)]">No one has paid on an open funeral yet.</li>
                            )}
                          </ul>
                        </div>
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Outstanding</p>
                          <ul className="mt-2 max-h-48 divide-y divide-[var(--rule)] overflow-y-auto">
                            {overview.payment_status.outstanding_members.map((m) => (
                              <li key={m.member_id} className="flex justify-between py-1.5 text-sm">
                                <span>{m.member_name}</span>
                                <span className="font-mono text-xs text-[var(--clay-red)]">{formatCedis(m.total_owed)}</span>
                              </li>
                            ))}
                            {overview.payment_status.outstanding_members.length === 0 && (
                              <li className="py-1.5 text-xs text-[var(--ink-soft)]">No one currently owes.</li>
                            )}
                          </ul>
                        </div>
                      </div>
                    </SectionCard>
                  )}

                  {overview.task_summary && (
                    <SectionCard title="Task oversight" eyebrow="Every task assigned within your family" accent="violet">
                      <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                        <div>
                          <p className="text-xs text-[var(--ink-soft)]">Pending</p>
                          <p className="font-display text-lg">{overview.task_summary.pending}</p>
                        </div>
                        <div>
                          <p className="text-xs text-[var(--ink-soft)]">In progress</p>
                          <p className="font-display text-lg">{overview.task_summary.in_progress}</p>
                        </div>
                        <div>
                          <p className="text-xs text-[var(--ink-soft)]">Awaiting you</p>
                          <p className="font-display text-lg text-[var(--gold)]">{overview.task_summary.awaiting_your_approval}</p>
                        </div>
                        <div>
                          <p className="text-xs text-[var(--ink-soft)]">Done</p>
                          <p className="font-display text-lg" style={{ color: "var(--forest)" }}>{overview.task_summary.done}</p>
                        </div>
                        <div>
                          <p className="text-xs text-[var(--ink-soft)]">Overdue</p>
                          <p className="font-display text-lg text-[var(--clay-red)]">{overview.task_summary.overdue}</p>
                        </div>
                      </div>
                      <div className="mt-3"><FolioLink href="/tasks">Open Tasks</FolioLink></div>
                    </SectionCard>
                  )}

                  {overview.tasks_awaiting_approval && overview.tasks_awaiting_approval.length > 0 && (
                    <SectionCard title="Tasks awaiting your approval" eyebrow={`${overview.tasks_awaiting_approval.length} submitted as done`} accent="gold">
                      <ul className="space-y-3">
                        {overview.tasks_awaiting_approval.map((t) => (
                          <li key={t.id} className="flex items-center justify-between gap-3 rounded-sm bg-white px-3 py-2">
                            <div>
                              <p className="text-sm font-medium">{t.title}</p>
                              <p className="text-xs text-[var(--ink-soft)]">
                                {t.assigned_to__full_name}
                                {t.due_date && ` · due ${new Date(t.due_date).toLocaleDateString()}`}
                              </p>
                            </div>
                            <div className="flex shrink-0 gap-2">
                              <button
                                onClick={() => decideTask.mutate({ id: t.id, approved: true })}
                                disabled={decideTask.isPending}
                                className="rounded-sm border border-[var(--forest)] px-2 py-1 text-xs text-[var(--forest)] disabled:opacity-50"
                              >
                                Approve
                              </button>
                              <Link href="/tasks" className="rounded-sm border border-[var(--rule)] px-2 py-1 text-xs text-[var(--ink-soft)] hover:border-[var(--clay-red)] hover:text-[var(--clay-red)]">
                                Reject…
                              </Link>
                            </div>
                          </li>
                        ))}
                      </ul>
                    </SectionCard>
                  )}

                  {overview.pending_expense_approvals && overview.pending_expense_approvals.length > 0 && (
                    <SectionCard title="Awaiting your decision" eyebrow={`${overview.pending_expense_approvals.length} purchase(s) to review`} accent="gold">
                      <ul className="space-y-3">
                        {overview.pending_expense_approvals.map((e) => (
                          <li key={e.id} className="flex items-center justify-between gap-3 rounded-sm bg-white px-3 py-2">
                            <div>
                              <p className="text-sm font-medium">{e.item_name} <span className="font-mono text-xs text-[var(--ink-soft)]">{formatCedis(e.amount)}</span></p>
                              <p className="text-xs text-[var(--ink-soft)]">
                                {e.funeral_event__deceased_name}&apos;s funeral · from {e.seller_name}
                                {e.recorded_by__username && ` · recorded by ${e.recorded_by__username}`}
                              </p>
                            </div>
                            <div className="flex shrink-0 gap-2">
                              <button
                                onClick={() => decideExpense.mutate({ expenseId: e.id, action: "approve" })}
                                disabled={decideExpense.isPending}
                                className="rounded-sm border border-[var(--forest)] px-2 py-1 text-xs text-[var(--forest)] disabled:opacity-50"
                              >
                                Approve
                              </button>
                              <button
                                onClick={() => decideExpense.mutate({ expenseId: e.id, action: "reject" })}
                                disabled={decideExpense.isPending}
                                className="rounded-sm border border-[var(--clay-red)] px-2 py-1 text-xs text-[var(--clay-red)] disabled:opacity-50"
                              >
                                Reject
                              </button>
                            </div>
                          </li>
                        ))}
                      </ul>
                    </SectionCard>
                  )}

                  {isFamilySecretary && overview.my_recorded_expenses && overview.my_recorded_expenses.length > 0 && (
                    <SectionCard title="What you've recorded" eyebrow="Your own submissions and their status" accent="violet">
                      <ul className="space-y-2">
                        {overview.my_recorded_expenses.map((e) => (
                          <li key={e.id} className="flex items-center justify-between text-sm">
                            <span>
                              {e.item_name} <span className="text-[var(--ink-soft)]">— {e.funeral_event__deceased_name}&apos;s funeral</span>
                            </span>
                            <span
                              className="rounded-full px-2 py-0.5 text-xs font-medium"
                              style={{
                                backgroundColor: e.status === "approved" ? "var(--forest-soft)" : e.status === "rejected" ? "var(--clay-red-soft)" : "var(--gold-soft)",
                                color: e.status === "approved" ? "var(--forest)" : e.status === "rejected" ? "var(--clay-red)" : "var(--gold)",
                              }}
                            >
                              {e.status}
                            </span>
                          </li>
                        ))}
                      </ul>
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

                  {overview.my_desk_assignments && overview.my_desk_assignments.length > 0 && (
                    <SectionCard title="Your desk assignments" eyebrow="Real, working desk access">
                      <ul className="space-y-1.5 text-sm">
                        {overview.my_desk_assignments.map((a) => (
                          <li key={a.funeral_event_id}>
                            <Link href="/front-desk" className="hover:text-[var(--forest)] hover:underline">
                              {a.desk_type.charAt(0).toUpperCase() + a.desk_type.slice(1)} desk
                            </Link>{" "}
                            <span className="text-[var(--ink-soft)]">— {a.funeral_event__deceased_name}&apos;s funeral</span>
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
