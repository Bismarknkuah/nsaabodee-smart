"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useDailyReport, useWeeklyReport, useMonthlyReport, useAnnualReport, useOutstandingMembers, useFamilyStatement, useExpenseStatement } from "@/lib/hooks/useReports";
import { useFamilies } from "@/lib/hooks/useFamilies";
import { formatCedis } from "@/lib/formatCedis";
import { reportsApi } from "@/lib/api/reports";
import { KpiTile, SectionCard } from "@/components/dashboard/DashboardVisuals";
import { IconMoney, IconWarning } from "@/components/icons/DashboardIcons";
import type { CollectionsReport } from "@/types/reports";

type Period = "daily" | "weekly" | "monthly" | "annual";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

export default function ReportsPage() {
  const [period, setPeriod] = useState<Period>("daily");
  const [dateInput, setDateInput] = useState(todayIso());
  const today = new Date();

  const daily = useDailyReport(dateInput);
  const weekly = useWeeklyReport(dateInput);
  const monthly = useMonthlyReport(today.getFullYear(), today.getMonth() + 1);
  const annual = useAnnualReport(today.getFullYear());

  const active = { daily, weekly, monthly, annual }[period];
  const report = active.data;

  // Same period the collections report already uses — one selector, every figure it claims to cover.
  const expenseRange = (() => {
    if (period === "daily") return { start: dateInput, end: dateInput };
    if (period === "weekly") {
      const start = new Date(dateInput);
      const end = new Date(start);
      end.setDate(start.getDate() + 6);
      return { start: dateInput, end: end.toISOString().slice(0, 10) };
    }
    if (period === "monthly") {
      const start = new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0, 10);
      return { start, end: todayIso() };
    }
    return { start: `${today.getFullYear()}-01-01`, end: todayIso() };
  })();

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Community Administration</p>
        <h1 className="font-display mt-1 text-4xl">Reports</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Every figure here is a read-only view over the contribution, gift, and expense
          ledgers — nothing on this page changes any of them.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-4 px-8 py-4">
        <div className="flex border border-[var(--rule)] bg-white text-xs">
          {(["daily", "weekly", "monthly", "annual"] as Period[]).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-4 py-1.5 font-mono font-medium uppercase tracking-wide ${period === p ? "bg-[var(--ink)] text-white" : "text-[var(--ink-soft)] hover:bg-[var(--surface)]"}`}
            >
              {p}
            </button>
          ))}
        </div>
        {(period === "daily" || period === "weekly") && (
          <input
            type="date"
            value={dateInput}
            onChange={(e) => setDateInput(e.target.value)}
            className="border-0 border-b-2 border-[var(--rule)] bg-transparent px-0 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
          />
        )}
      </div>

      <main className="grid gap-6 px-8 pb-16 lg:grid-cols-2">
        <section className="lg:col-span-2">
          <div className="mb-3 flex justify-end">
            <button
              onClick={() =>
                reportsApi.openCollectionsPdf(
                  period,
                  period === "daily"
                    ? `date=${dateInput}`
                    : period === "weekly"
                    ? `week_start=${dateInput}`
                    : period === "monthly"
                    ? `year=${today.getFullYear()}&month=${today.getMonth() + 1}`
                    : `year=${today.getFullYear()}`
                )
              }
              className="border border-[var(--ink)] px-3 py-1.5 font-mono text-[11px] font-medium uppercase tracking-wide text-[var(--ink)] hover:bg-[var(--ink)] hover:text-white"
            >
              Download PDF statement
            </button>
          </div>
          {active.isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
          {report && <CollectionsReportCard report={report} />}
        </section>

        <ExpensesSection startDate={expenseRange.start} endDate={expenseRange.end} />
        <FamilyStatementLookup />
        <OutstandingMembersPanel />
      </main>
    </div>
  );
}

function ExpensesSection({ startDate, endDate }: { startDate: string; endDate: string }) {
  const { data, isLoading } = useExpenseStatement(startDate, endDate);
  return (
    <SectionCard title="Expenses" eyebrow={data ? `${data.expense_count} recorded` : "This period"} accent="clay">
      {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
      {data && (
        <>
          <KpiTile label="Total spent" value={formatCedis(data.total)} color="clay" icon={<IconWarning />} />
          {Object.keys(data.by_category).length > 0 ? (
            <table className="mt-3 w-full border-collapse text-sm">
              <tbody>
                {Object.entries(data.by_category).map(([category, amount]) => (
                  <tr key={category} className="border-b border-[var(--rule)] last:border-0">
                    <td className="py-2 capitalize text-[var(--ink-soft)]">{category.replace("_", " ")}</td>
                    <td className="py-2 text-right font-mono">{formatCedis(amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="mt-3 text-sm text-[var(--ink-soft)]">Nothing recorded for this period.</p>
          )}
          <p className="mt-3 text-xs text-[var(--ink-soft)]">
            Recorded per funeral, on each funeral&apos;s own page — this is the community-wide
            total across every one of them for the period selected above.
          </p>
        </>
      )}
    </SectionCard>
  );
}

function CollectionsReportCard({ report }: { report: CollectionsReport }) {
  return (
    <div className="grid gap-4 sm:grid-cols-3">
      <SectionCard title="Contributions" eyebrow={`${report.contributions.count} payment(s)`} accent="forest">
        <KpiTile label="Total" value={formatCedis(report.contributions.total)} color="forest" icon={<IconMoney />} />
        <MethodTable breakdown={report.contributions.by_method} />
      </SectionCard>
      <SectionCard title="Gift cash" eyebrow={`${report.gift_cash.count} cash donation(s)`} accent="violet">
        <KpiTile label="Total" value={formatCedis(report.gift_cash.total)} color="violet" icon={<IconMoney />} />
        <MethodTable breakdown={report.gift_cash.by_method} />
      </SectionCard>
      <SectionCard title="Combined cash in hand" eyebrow={`${report.receipts_issued} receipt(s) issued`} accent="gold">
        <KpiTile
          label="Total"
          value={formatCedis((Number(report.contributions.total) + Number(report.gift_cash.total)).toString())}
          color="gold" icon={<IconMoney />}
        />
        <MethodTable breakdown={report.combined_cash_position_by_method} />
      </SectionCard>
    </div>
  );
}

function MethodTable({ breakdown }: { breakdown: CollectionsReport["contributions"]["by_method"] }) {
  return (
    <table className="mt-3 w-full border-collapse text-xs">
      <tbody>
        {Object.entries(breakdown).map(([method, amount]) => (
          <tr key={method} className="border-b border-[var(--rule)] last:border-0">
            <td className="py-1.5 capitalize text-[var(--ink-soft)]">{method.replace("_", " ")}</td>
            <td className="py-1.5 text-right font-mono">{formatCedis(amount)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function FamilyStatementLookup() {
  const { data: families } = useFamilies(false);
  const [familyId, setFamilyId] = useState("");
  const { data: statement } = useFamilyStatement(familyId);

  return (
    <div className="lg:col-span-2">
      <SectionCard title="Family statement" eyebrow="The abusuapanin's view" accent="forest">
        <select
          value={familyId}
          onChange={(e) => setFamilyId(e.target.value)}
          className="w-full max-w-sm border border-[var(--rule)] px-3 py-2 text-sm"
        >
          <option value="">Choose a family…</option>
          {families?.filter((f) => f.status === "active").map((f) => (
            <option key={f.id} value={f.id}>{f.name}</option>
          ))}
        </select>

        {statement && (
          <div className="mt-4 space-y-4">
            <div className="grid grid-cols-2 gap-px border border-[var(--rule)] bg-[var(--rule)] sm:grid-cols-4">
              <KpiTile label="Family expected" value={formatCedis(statement.family_ledger.expected_total)} color="forest" />
              <KpiTile label="Family collected" value={formatCedis(statement.family_ledger.collected_total)} color="forest" />
              <KpiTile label="Community expected" value={formatCedis(statement.community_ledger.expected_total)} color="gold" />
              <KpiTile label="Community collected" value={formatCedis(statement.community_ledger.collected_total)} color="gold" />
            </div>

            {statement.guest_ledger && statement.town_leaders_ledger ? (
              <div className="grid grid-cols-2 gap-px border border-[var(--rule)] bg-[var(--rule)]">
                <KpiTile label={`Guest ledger — ${statement.guest_ledger.donor_count} donors`} value={formatCedis(statement.guest_ledger.total_value)} color="violet" />
                <KpiTile label={`Town leaders — ${statement.town_leaders_ledger.donor_count} donors`} value={formatCedis(statement.town_leaders_ledger.total_value)} color="violet" />
              </div>
            ) : (
              <p className="border border-dashed border-[var(--rule)] p-3 text-xs text-[var(--ink-soft)]">
                Guest and Town Leaders ledger figures are only shown to this family&apos;s own
                head or a community administrator.
              </p>
            )}

            {statement.donation_receivers && statement.donation_receivers.length > 0 && (
              <div>
                <p className="font-mono text-[10px] font-medium uppercase tracking-[0.16em] text-[var(--ink-soft)]">
                  Donation accountability — who received what
                </p>
                <table className="mt-2 w-full border-collapse border border-[var(--rule)] text-sm">
                  <tbody>
                    {statement.donation_receivers.map((r) => (
                      <tr key={r.member_id} className="border-b border-[var(--rule)] last:border-0">
                        <td className="px-3 py-2">{r.member_name}</td>
                        <td className="px-3 py-2 text-right font-mono">{formatCedis(r.total_received)} ({r.donation_count})</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <Row label="Members as outsiders elsewhere — expected" value={formatCedis(statement.members_as_outsiders_elsewhere.expected_total)} />
            <Row label="Members as outsiders elsewhere — collected" value={formatCedis(statement.members_as_outsiders_elsewhere.collected_total)} />

            <button
              onClick={() => reportsApi.openFamilyStatementPdf(familyId)}
              className="border border-[var(--rule)] px-3 py-1.5 font-mono text-[11px] font-medium uppercase tracking-wide hover:border-[var(--forest)] hover:text-[var(--forest)]"
            >
              Download PDF statement
            </button>
          </div>
        )}
      </SectionCard>
    </div>
  );
}

function OutstandingMembersPanel() {
  const { data } = useOutstandingMembers();
  return (
    <SectionCard title="Outstanding members" eyebrow={`${data?.members.length ?? 0} listed`} accent="clay">
      <p className="-mt-2 mb-3 text-sm text-[var(--ink-soft)]">
        Owes money on a currently open funeral — different from the Defaulters Dashboard,
        which only counts funerals that have already closed.
      </p>
      <ul className="max-h-64 divide-y divide-[var(--rule)] overflow-y-auto border-y border-[var(--rule)]">
        {data?.members.map((m) => (
          <li key={m.member_id} className="flex items-center justify-between py-2 text-sm">
            <span>{m.member_name}</span>
            <span className="font-mono text-[var(--clay-red)]">{formatCedis(m.total_owed)}</span>
          </li>
        ))}
        {data?.members.length === 0 && <li className="py-2 text-sm text-[var(--ink-soft)]">Nobody owes anything right now.</li>}
      </ul>
    </SectionCard>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-[var(--rule)] pb-1 text-sm">
      <span className="text-[var(--ink-soft)]">{label}</span>
      <span className="font-mono font-medium">{value}</span>
    </div>
  );
}
