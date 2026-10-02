"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { dashboardApi } from "@/lib/api/dashboard";
import { formatCedis } from "@/lib/formatCedis";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";
import { KpiTile, SectionCard, FolioLink } from "@/components/dashboard/DashboardVisuals";
import { MyOutstandingObligationsCard } from "@/components/dashboard/MyOutstandingObligationsCard";

interface MemberOverview {
  membership_number?: string;
  defaulter_tier?: string;
  missed_contributions_count?: number;
  active_funerals?: { id: string; deceased_name: string; deceased_family_name: string }[];
  message?: string;
  donations_received?: { total_received: string; donation_count: number } | null;
  family_info?: { family_id: string; family_name: string; family_head_name: string | null; family_secretary_name: string | null; family_treasurer_name: string | null } | null;
  upcoming_meetings?: { id: string; title: string; scheduled_for: string; location: string; family_id: string | null }[];
  welfare_obligations?: { id: string; campaign__title: string; campaign__category__name: string; expected_amount: string; amount_paid: string }[];
  my_tasks?: { id: string; title: string; status: string; due_date: string | null; funeral_event__deceased_name: string | null }[];
  // 'Community members should see, or be billed on, the welfare amount' — and the rest of their money, first.
  profile?: { full_name: string; membership_number: string; status: string; phone: string; email: string; family_name: string | null; ledger: string; member_id: string };
  home_totals?: { paid_this_year: string; paid_all_time: string; outstanding_total: string; family_member_count: number };
  recent_payments?: { id: string; paid_at: string; description: string; method: string; amount: string; status: string; receipt_number: string | null }[];
  contribution_summary?: { your_rate: string; last_payment_at: string | null; next_due: { deceased_name: string; balance: string; collection_start_date: string } | null; up_to_date: boolean };
  announcements?: { id: string; title: string; at: string; image_url: string | null }[];
  money?: { owing_now: string; arrears_total: string; welfare_owing: string; paid_this_year: string; wallet_balance: string; must_clear_arrears_first: boolean };
  open_bills?: { obligation_id: string; funeral_id: string; deceased_name: string; rate_type: string; expected_amount: string; amount_paid: string; balance: string }[];
  arrears?: { obligation_id: string; funeral_id: string; deceased_name: string; expected_amount: string; amount_paid: string; balance: string; collection_start_date: string }[];
  welfare_bills?: { obligation_id: string; campaign: string; scope: string; expected_amount: string; amount_paid: string; balance: string }[];
}
interface CommitteePositionOverview {
  funeral_id: string;
  deceased_name: string;
  your_title: string;
  task_summary: { total: number; done: number; pending_approval: number };
  contribution_summary: { total_expected?: string; total_collected?: string };
  attendance_count: number;
  upcoming_meetings: { id: string; title: string; scheduled_for: string; location: string }[];
}

/** Quieter than any other dashboard on purpose — this is one person looking up their own entry in the register, not running operations. Single column, generous space, no dense tile grid. */
export default function MemberDashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const overview = data?.sections.member_overview as MemberOverview | undefined;
  const inGoodStanding = overview?.defaulter_tier === "none";
  const committeePositions = data?.sections.committee_positions as CommitteePositionOverview[] | undefined;

  return (
    <DashboardPageShell folio="Folio VI" register="Membership Record" title={overview?.profile ? `Welcome, ${overview.profile.full_name}` : "Your Standing"} subtitle="Your community. Your family. Our strength.">
      {isLoading && <p className="text-sm text-[var(--text-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}

      {overview && (
        <div className="lg:col-span-2 w-full space-y-6">
          {overview.message && <p className="text-center text-sm text-[var(--text-soft)]">{overview.message}</p>}
          {overview.profile && overview.home_totals && <MemberHome overview={overview} />}

          {/* Identity — who you are in this register, first and clearest */}
          {overview.membership_number && (
            <div className="border-2 p-8 text-center" style={{ borderColor: inGoodStanding ? "var(--forest)" : "var(--clay-red)" }}>
              <p className="font-mono text-xs uppercase tracking-[0.16em] text-[var(--text-soft)]">{overview.membership_number}</p>
              <p className="font-display mt-3 text-2xl" style={{ color: inGoodStanding ? "var(--forest)" : "var(--clay-red)" }}>
                {inGoodStanding ? "In good standing" : `${overview.defaulter_tier?.replace(/_/g, " ")}`}
              </p>
              {!inGoodStanding && (
                <p className="mt-1 text-sm text-[var(--text-soft)]">{overview.missed_contributions_count} missed contribution(s)</p>
              )}

              <div className="mt-6 flex flex-wrap justify-center gap-3">
                <FolioLink href="/my-receipts">My receipts</FolioLink>
                {overview.donations_received !== null && overview.donations_received !== undefined && (
                  <FolioLink href="/my-donations-received">Donations given in my name</FolioLink>
                )}
              </div>
            </div>
          )}

          {overview.money && <MemberMoney overview={overview} />}

          {/* What needs your attention — a real balance to pay is the single most actionable thing here */}
          <MyOutstandingObligationsCard />

          {overview.my_tasks && overview.my_tasks.length > 0 && (
            <SectionCard title="Your tasks" eyebrow="Assigned to you" accent="clay">
              <ul className="divide-y divide-[var(--border-soft)]">
                {overview.my_tasks.map((t) => (
                  <li key={t.id} className="flex items-center justify-between gap-3 py-2 text-sm">
                    <div>
                      <p>{t.title}</p>
                      {t.funeral_event__deceased_name && (
                        <p className="text-xs text-[var(--text-soft)]">{t.funeral_event__deceased_name}&apos;s funeral</p>
                      )}
                    </div>
                    <div className="text-right">
                      <span className="rounded-lg bg-[var(--bg)] px-2 py-0.5 text-xs capitalize text-[var(--text-soft)]">
                        {t.status.replace(/_/g, " ")}
                      </span>
                      {t.due_date && <p className="mt-1 text-xs text-[var(--text-soft)]">Due {new Date(t.due_date).toLocaleDateString()}</p>}
                    </div>
                  </li>
                ))}
              </ul>
              <div className="mt-3"><FolioLink href="/tasks">Open Tasks</FolioLink></div>
            </SectionCard>
          )}


          {committeePositions && committeePositions.length > 0 && (
            <div className="space-y-4">
              {committeePositions.map((p) => (
                <SectionCard key={p.funeral_id} title={p.your_title} eyebrow={`${p.deceased_name}'s funeral committee`} accent="violet">
                  <div className="grid grid-cols-3 gap-3 text-sm">
                    <div>
                      <p className="text-xs text-[var(--text-soft)]">Tasks</p>
                      <p className="font-display text-lg">{p.task_summary.done}/{p.task_summary.total}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[var(--text-soft)]">Attendance</p>
                      <p className="font-display text-lg">{p.attendance_count}</p>
                    </div>
                    <div>
                      <p className="text-xs text-[var(--text-soft)]">Pending approval</p>
                      <p className="font-display text-lg">{p.task_summary.pending_approval}</p>
                    </div>
                  </div>
                  {p.upcoming_meetings.length > 0 && (
                    <ul className="mt-3 space-y-1 border-t border-[var(--border)] pt-3">
                      {p.upcoming_meetings.map((m) => (
                        <li key={m.id} className="text-xs text-[var(--text-soft)]">
                          {m.title}, {new Date(m.scheduled_for).toLocaleDateString()}
                        </li>
                      ))}
                    </ul>
                  )}
                  <div className="mt-3"><FolioLink href={`/funerals/${p.funeral_id}`}>Open this funeral</FolioLink></div>
                </SectionCard>
              ))}
            </div>
          )}

          {overview.upcoming_meetings && overview.upcoming_meetings.length > 0 && (
            <SectionCard title="Meeting invitations" accent="forest">
              <ul className="space-y-3">
                {overview.upcoming_meetings.map((m) => (
                  <li key={m.id} className="border-l-2 border-[var(--forest)] pl-3">
                    <p className="text-sm font-medium">
                      {m.title}
                      {!m.family_id && <span className="ml-2 text-xs text-[var(--text-soft)]">(community-wide)</span>}
                    </p>
                    <p className="text-xs text-[var(--text-soft)]">
                      {new Date(m.scheduled_for).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })}
                      {m.location && ` · ${m.location}`}
                    </p>
                  </li>
                ))}
              </ul>
            </SectionCard>
          )}

          {overview.family_info && (
            <SectionCard title="Your family" eyebrow={overview.family_info.family_name} accent="violet">
              <ul className="space-y-1 text-sm">
                {overview.family_info.family_head_name && <li>Family Head: {overview.family_info.family_head_name}</li>}
                {overview.family_info.family_secretary_name && <li>Family Secretary: {overview.family_info.family_secretary_name}</li>}
                {overview.family_info.family_treasurer_name && <li>Family Treasurer: {overview.family_info.family_treasurer_name}</li>}
              </ul>
              <div className="mt-3"><FolioLink href={`/family-fund/${overview.family_info.family_id}`}>Family fund</FolioLink></div>
            </SectionCard>
          )}

          {overview.active_funerals && overview.active_funerals.length > 0 && (
            <SectionCard title="Active funerals in your community" accent="clay">
              <ul className="divide-y divide-[var(--border-soft)]">
                {overview.active_funerals.map((f) => (
                  <li key={f.id} className="py-2 text-sm">
                    <Link href={`/funerals/${f.id}`} className="hover:text-[var(--forest)] hover:underline">
                      {f.deceased_name} <span className="text-[var(--text-soft)]">, {f.deceased_family_name}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </SectionCard>
          )}

          {overview.welfare_obligations && overview.welfare_obligations.length > 0 && (
            <SectionCard title="Welfare & contributions" eyebrow="Beyond funerals" accent="gold">
              <ul className="divide-y divide-[var(--border-soft)]">
                {overview.welfare_obligations.map((o) => (
                  <li key={o.id} className="flex items-center justify-between py-2 text-sm">
                    <div>
                      <p>{o.campaign__title}</p>
                      <p className="text-xs text-[var(--text-soft)]">{o.campaign__category__name}</p>
                    </div>
                    <span className="font-mono text-xs">
                      {formatCedis(o.amount_paid)} / {formatCedis(o.expected_amount)}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="mt-3"><FolioLink href="/welfare-contributions">Open Welfare & Contributions</FolioLink></div>
            </SectionCard>
          )}
        </div>
      )}
    </DashboardPageShell>
  );
}


/**
 * The member's money, first and plainest: what is owed now (open funerals), arrears (closed funerals, which must be
 * cleared before a newer funeral can be paid), welfare, wallet — each bill with a way to pay. This is the member
 * login's whole purpose: a community member account plays no other role.
 */
function MemberMoney({ overview }: { overview: MemberOverview }) {
  const m = overview.money!;
  const bills = overview.open_bills ?? []; const arrears = overview.arrears ?? []; const welfare = overview.welfare_bills ?? [];
  const Row = ({ title, sub, paid, expected, balance, pay }: { title: string; sub?: string; paid: string; expected: string; balance: string; pay?: string }) => (
    <li className="flex items-center justify-between gap-3 py-2.5 text-sm">
      <div><p className="font-medium">{title}</p>{sub && <p className="text-xs text-[var(--text-soft)]">{sub}</p>}</div>
      <div className="text-right">
        <p className="font-mono">{formatCedis(paid)} / {formatCedis(expected)}</p>
        {Number(balance) > 0 ? (
          <p className="text-xs" style={{ color: "var(--clay-red)" }}>owes {formatCedis(balance)}{pay && <> · <Link href={pay} className="font-medium text-[var(--primary)] hover:underline">Pay</Link></>}</p>
        ) : <p className="text-xs" style={{ color: "var(--forest)" }}>paid in full</p>}
      </div>
    </li>
  );
  return (
    <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KpiTile label="Owing now" value={formatCedis(m.owing_now)} color={Number(m.owing_now) > 0 ? "clay" : "forest"} />
        <KpiTile label="Arrears" value={formatCedis(m.arrears_total)} color={Number(m.arrears_total) > 0 ? "clay" : "forest"} />
        <KpiTile label="Welfare owing" value={formatCedis(m.welfare_owing)} color={Number(m.welfare_owing) > 0 ? "gold" : "forest"} />
        <KpiTile label="Wallet credit" value={formatCedis(m.wallet_balance)} color="violet" />
      </div>
      {m.must_clear_arrears_first && <p className="rounded-lg bg-[var(--gold-soft)] px-4 py-2 text-xs">You still owe on an older funeral. Clear that first — a newer funeral cannot be paid while an older one is owed.</p>}
      <SectionCard title="Your funeral bills" eyebrow={`Paid ${formatCedis(m.paid_this_year)} this year`} accent="clay">
        <ul className="divide-y divide-[var(--border-soft)]">
          {arrears.map((b) => <Row key={b.obligation_id} title={b.deceased_name} sub={`Arrears · funeral closed · ${new Date(b.collection_start_date).toLocaleDateString()}`} paid={b.amount_paid} expected={b.expected_amount} balance={b.balance} pay={`/pay-momo/${b.obligation_id}`} />)}
          {bills.map((b) => <Row key={b.obligation_id} title={b.deceased_name} sub={`Open · ${b.rate_type.replace("_", " ")} rate`} paid={b.amount_paid} expected={b.expected_amount} balance={b.balance} pay={m.must_clear_arrears_first ? undefined : `/pay-momo/${b.obligation_id}`} />)}
          {bills.length === 0 && arrears.length === 0 && <li className="py-2 text-xs text-[var(--text-soft)]">No funeral bill at the moment.</li>}
        </ul>
      </SectionCard>
      <SectionCard title="Your welfare contributions" eyebrow="Set by the Community Welfare Manager — community-wide, or for your family once your Head and Secretary approve" accent="gold">
        <ul className="divide-y divide-[var(--border-soft)]">
          {welfare.map((w) => <Row key={w.obligation_id} title={w.campaign} sub={w.scope === "family" ? "Your family's welfare" : "Community welfare contribution"} paid={w.amount_paid} expected={w.expected_amount} balance={w.balance} />)}
          {welfare.length === 0 && <li className="py-2 text-xs text-[var(--text-soft)]">No welfare contribution is due.</li>}
        </ul>
        <div className="mt-3"><FolioLink href="/welfare-contributions">Pay welfare, or ask for support</FolioLink></div>
      </SectionCard>
    </>
  );
}


const METHOD_LABEL: Record<string, string> = { cash: "Cash", mobile_money: "MoMo", bank: "Bank", other: "Other", wallet: "Wallet" };

/**
 * The member's home, as in the reference design: four figures, who you are beside your recent payments, a contribution
 * summary with your standing, and a rail of the things a member actually does — pay, see history, their family, the
 * community's announcements. Nothing here that a member cannot use.
 */
function MemberHome({ overview }: { overview: MemberOverview }) {
  const p = overview.profile!; const t = overview.home_totals!; const cs = overview.contribution_summary; const owes = Number(t.outstanding_total) > 0;
  const Tile = ({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) => (
    <div className="flex items-center gap-3 rounded-[var(--radius)] bg-[var(--card)] p-4" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
      <span aria-hidden className="h-10 w-10 shrink-0 rounded-xl" style={{ backgroundColor: color, opacity: 0.9 }} />
      <div><p className="text-xs text-[var(--text-soft)]">{label}</p><p className="text-xl font-semibold" style={{ color }}>{value}</p><p className="text-[11px] text-[var(--text-soft)]">{sub}</p></div>
    </div>
  );
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_280px]">
      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Tile label="Total contributions" value={formatCedis(t.paid_this_year)} sub="Paid this year" color="var(--primary)" />
          <Tile label="Outstanding balance" value={formatCedis(t.outstanding_total)} sub={owes ? "Due now" : "No dues"} color={owes ? "var(--clay-red)" : "var(--forest)"} />
          <Tile label="Total payments" value={formatCedis(t.paid_all_time)} sub="All time" color="var(--violet, #6d4bd1)" />
          <Tile label="Family members" value={String(t.family_member_count)} sub={p.family_name ? `${p.family_name} family` : "Registered"} color="var(--gold)" />
        </div>
        <div className="grid gap-6 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          <div className="rounded-[var(--radius)] bg-[var(--card)] p-5" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
            <div className="flex items-center gap-4">
              <span aria-hidden className="flex h-16 w-16 items-center justify-center rounded-full bg-[var(--bg)] text-2xl font-semibold text-[var(--text-soft)]">{p.full_name.split(" ").map((w) => w[0]).slice(0, 2).join("")}</span>
              <div><p className="text-lg font-semibold">{p.full_name}</p><span className="rounded-full px-2 py-0.5 text-[10px] font-semibold capitalize text-white" style={{ backgroundColor: p.status === "active" ? "var(--forest)" : "var(--clay-red)" }}>{p.status}</span></div>
            </div>
            <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
              <dt className="text-[var(--text-soft)]">Member ID</dt><dd className="font-mono">{p.membership_number}</dd>
              <dt className="text-[var(--text-soft)]">Phone</dt><dd>{p.phone || "—"}</dd>
              <dt className="text-[var(--text-soft)]">Email</dt><dd className="truncate">{p.email || "—"}</dd>
              <dt className="text-[var(--text-soft)]">Family</dt><dd>{p.family_name ?? "—"}{p.ledger === "town_elders" ? " · Town Elders ledger" : ""}</dd>
            </dl>
            <div className="mt-4"><FolioLink href="/profile">View full profile</FolioLink></div>
          </div>
          <div className="rounded-[var(--radius)] bg-[var(--card)] p-5" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
            <div className="flex items-center justify-between"><p className="font-semibold">Recent payments</p><Link href="/my-receipts" className="text-xs text-[var(--primary)] hover:underline">View all</Link></div>
            <table className="mt-2 w-full text-xs">
              <thead><tr className="border-b border-[var(--border)] text-left uppercase tracking-wide text-[var(--text-soft)]"><th className="py-1.5 font-medium">Date</th><th className="py-1.5 font-medium">Description</th><th className="py-1.5 font-medium">Method</th><th className="py-1.5 text-right font-medium">Amount</th><th className="py-1.5 text-right font-medium">Status</th></tr></thead>
              <tbody className="divide-y divide-[var(--border-soft)]">
                {(overview.recent_payments ?? []).map((r) => (
                  <tr key={r.id}><td className="py-1.5">{new Date(r.paid_at).toLocaleDateString()}</td><td className="py-1.5">{r.description}</td><td className="py-1.5">{METHOD_LABEL[r.method] ?? r.method}</td><td className="py-1.5 text-right font-mono">{formatCedis(r.amount)}</td><td className="py-1.5 text-right"><span className="rounded-full px-2 py-0.5 text-[10px] font-semibold text-white" style={{ backgroundColor: "var(--forest)" }}>Paid</span></td></tr>
                ))}
                {(overview.recent_payments ?? []).length === 0 && <tr><td colSpan={5} className="py-3 text-[var(--text-soft)]">No payment recorded yet.</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
        {cs && (
          <div className="rounded-[var(--radius)] bg-[var(--card)] p-5" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
            <p className="font-semibold">Contribution summary</p>
            <div className="mt-3 grid gap-4 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
              <dl className="grid grid-cols-3 gap-3 text-sm">
                <div><dt className="text-xs text-[var(--text-soft)]">Your contribution rate</dt><dd className="font-semibold">{formatCedis(cs.your_rate)}</dd></div>
                <div><dt className="text-xs text-[var(--text-soft)]">Last payment</dt><dd className="font-semibold">{cs.last_payment_at ? new Date(cs.last_payment_at).toLocaleDateString() : "—"}</dd></div>
                <div><dt className="text-xs text-[var(--text-soft)]">Next due</dt><dd className="font-semibold">{cs.next_due ? `${formatCedis(cs.next_due.balance)} · ${cs.next_due.deceased_name}` : "Nothing due"}</dd></div>
              </dl>
              <div className="flex items-center gap-3 rounded-lg px-4 py-3 text-sm" style={{ backgroundColor: cs.up_to_date ? "rgba(46,125,50,0.08)" : "rgba(192,57,43,0.08)" }}>
                <span aria-hidden className="text-lg">{cs.up_to_date ? "✓" : "!"}</span>
                <div><p className="font-semibold">{cs.up_to_date ? "You are up to date!" : `You owe ${formatCedis(t.outstanding_total)}`}</p><p className="text-xs text-[var(--text-soft)]">{cs.up_to_date ? "No outstanding payments." : "Pay from your funeral bills below."}</p></div>
              </div>
            </div>
          </div>
        )}
      </div>
      <aside className="space-y-4">
        <div className="rounded-[var(--radius)] bg-[var(--card)] p-4" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
          <p className="text-sm font-semibold">Quick actions</p>
          <div className="mt-2 space-y-2 text-sm">
            {[["/welfare-contributions", "Make a payment"], ["/my-receipts", "View payment history"], ["/profile", "My details"], ["/#announcements", "View announcements"]].map(([href, label]) => (
              <Link key={label} href={href} className="block rounded-lg bg-[var(--bg)] px-3 py-2 font-medium hover:bg-[var(--gold-soft)]">{label}</Link>
            ))}
          </div>
        </div>
        <div className="rounded-[var(--radius)] bg-[var(--card)] p-4" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
          <p className="text-sm font-semibold">Recent announcements</p>
          <ul className="mt-2 divide-y divide-[var(--border-soft)] text-sm">
            {(overview.announcements ?? []).map((a) => <li key={a.id} className="py-2"><p className="font-medium">{a.title}</p><p className="text-[11px] text-[var(--text-soft)]">{new Date(a.at).toLocaleDateString()}</p></li>)}
            {(overview.announcements ?? []).length === 0 && <li className="py-2 text-xs text-[var(--text-soft)]">No announcements yet.</li>}
          </ul>
        </div>
      </aside>
    </div>
  );
}
