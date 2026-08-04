"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  useFamilyFunds, useCreateFamilyFund, useFundContributions, useFundSummary, useContributeToFund, useAssignFamilyOfficer,
  useFamilyOfficerPositions, useAppointFamilyOfficerPosition, useRemoveFamilyOfficerPosition,
} from "@/lib/hooks/useFamilyFunds";
import { useFamilies } from "@/lib/hooks/useFamilies";
import { useFunerals } from "@/lib/hooks/useFunerals";
import { useAuthStore } from "@/store/authStore";
import {
  useFuneralExpenses, useExpenditureSummary, useRecordFuneralExpense, useDecideFuneralExpense,
  useFamilyFinancialOverview,
} from "@/lib/hooks/useFamilyFunds";
import { familyFuneralExpensesApi } from "@/lib/api/familyFunds";
import { membersApi } from "@/lib/api/members";
import { familyFundsApi, SUGGESTED_FAMILY_OFFICER_TITLES } from "@/lib/api/familyFunds";
import { openReceiptPrintWindow } from "@/lib/openReceiptPrintWindow";
import { PrintReceiptButton } from "@/components/PrintReceiptButton";
import { authFetch } from "@/lib/api/authFetch";
import { formatCedis } from "@/lib/formatCedis";
import type { FamilyFund, FundPaymentMethod } from "@/types/familyFund";

export default function FamilyFundPage() {
  const { familyId } = useParams<{ familyId: string }>();
  const { data: families } = useFamilies(false);
  const family = families?.find((f) => f.id === familyId);
  const currentUser = useAuthStore((s) => s.user);
  const isFamilyHead = currentUser?.role === "family_head";

  const { data: funds, isLoading, isError, error } = useFamilyFunds(familyId);
  const createFund = useCreateFamilyFund(familyId);
  const [showCreate, setShowCreate] = useState(false);
  const [selectedFund, setSelectedFund] = useState<FamilyFund | null>(null);

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
          Private — never part of the community ledger
        </p>
        <div className="mt-1 flex items-start justify-between gap-4">
          <div>
            <h1 className="font-display text-4xl">{family?.name ?? "Family"} Fund</h1>
            <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
              Your family&apos;s own contribution fund. Members can give any amount they
              choose — there's no fixed rate. Only the family head, the family secretary,
              and the family treasurer can see this page.
            </p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="shrink-0 bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white"
          >
            New fund
          </button>
        </div>
      </header>

      <main className="px-8 py-8">
        <FamilyFinancialOverviewCard familyId={familyId} />

        {isFamilyHead && <AssignOfficerPanel familyId={familyId} family={family} />}
        <FamilyOfficerPositionsPanel familyId={familyId} isFamilyHead={isFamilyHead} />

        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
        {isError && (
          <div className="rounded-sm border border-dashed border-[var(--clay-red)] p-6 text-center">
            <p className="text-sm text-[var(--clay-red)]">{error?.message ?? "Not permitted."}</p>
          </div>
        )}

        {funds?.length === 0 && (
          <div className="rounded-sm border border-dashed border-[var(--rule)] px-6 py-10 text-center">
            <p className="font-display text-lg">No funds yet</p>
            <p className="mt-1 text-sm text-[var(--ink-soft)]">Create one to start collecting.</p>
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-2">
          {funds?.map((fund) => (
            <FundCard key={fund.id} familyId={familyId} fund={fund} onOpen={() => setSelectedFund(fund)} />
          ))}
        </div>

        <FuneralExpensesPanel familyId={familyId} />
      </main>

      {showCreate && (
        <CreateFundDialog
          onClose={() => setShowCreate(false)}
          onCreate={(name, description) => createFund.mutate({ name, description }, { onSuccess: () => setShowCreate(false) })}
          isPending={createFund.isPending}
          error={createFund.error?.message}
        />
      )}
      {selectedFund && (
        <FundDetailDialog familyId={familyId} fund={selectedFund} onClose={() => setSelectedFund(null)} />
      )}
    </div>
  );
}

function FundCard({ familyId, fund, onOpen }: { familyId: string; fund: FamilyFund; onOpen: () => void }) {
  const { data: summary } = useFundSummary(familyId, fund.id);
  return (
    <button
      onClick={onOpen}
      className="rounded-sm border border-[var(--rule)] bg-white p-4 text-left hover:border-[var(--forest)]"
    >
      <p className="font-display text-lg">{fund.name}</p>
      {fund.description && <p className="mt-1 text-sm text-[var(--ink-soft)]">{fund.description}</p>}
      {summary && (
        <div className="mt-3 flex items-center gap-6">
          <div>
            <p className="text-xs text-[var(--ink-soft)]">Total collected</p>
            <p className="font-mono text-xl font-semibold">{formatCedis(summary.total_collected)}</p>
          </div>
          <div>
            <p className="text-xs text-[var(--ink-soft)]">Contributors</p>
            <p className="font-mono text-xl font-semibold">{summary.contributor_count}</p>
          </div>
        </div>
      )}
    </button>
  );
}

function CreateFundDialog({
  onClose, onCreate, isPending, error,
}: { onClose: () => void; onCreate: (name: string, description: string) => void; isPending: boolean; error?: string }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="font-body w-full max-w-sm rounded-sm bg-[var(--surface)] p-6 text-[var(--ink)] shadow-xl">
        <h2 className="font-display text-xl">New family fund</h2>
        <div className="mt-4 space-y-3">
          <div>
            <label className="text-sm font-medium">Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. School Fees Fund"
              className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
          </div>
          <div>
            <label className="text-sm font-medium">Description (optional)</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
          </div>
          {error && <p className="text-sm text-[var(--clay-red)]">{error}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <button onClick={onClose} className="px-3 py-2 text-sm text-[var(--ink-soft)]">Cancel</button>
            <button
              onClick={() => onCreate(name, description)}
              disabled={isPending || !name.trim()}
              className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {isPending ? "Creating…" : "Create fund"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function FundDetailDialog({ familyId, fund, onClose }: { familyId: string; fund: FamilyFund; onClose: () => void }) {
  const { data: contributions } = useFundContributions(familyId, fund.id);
  const { data: summary } = useFundSummary(familyId, fund.id);
  const contribute = useContributeToFund(familyId, fund.id);

  const [query, setQuery] = useState("");
  const [memberId, setMemberId] = useState("");
  const [memberName, setMemberName] = useState("");
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState<FundPaymentMethod>("cash");

  const { data: memberResults } = useQuery({
    queryKey: ["fund-member-search", query],
    queryFn: () => membersApi.list({ search: query }),
    enabled: query.trim().length >= 2 && !memberId,
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!memberId || !amount) return;
    contribute.mutate(
      { member_id: memberId, amount, payment_method: method },
      {
        onSuccess: () => {
          setMemberId(""); setMemberName(""); setQuery(""); setAmount("");
        },
      }
    );
  };

  const viewReceipt = async (contributionId: string) => {
    const text = await familyFundsApi.receiptText(familyId, fund.id, contributionId);
    openReceiptPrintWindow(text);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="font-body max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-sm bg-[var(--surface)] p-6 text-[var(--ink)] shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <h2 className="font-display text-xl">{fund.name}</h2>
          <button onClick={onClose} className="text-[var(--ink-soft)] hover:text-[var(--ink)]" aria-label="Close">✕</button>
        </div>

        {summary && (
          <div className="mt-3 flex gap-6 text-sm">
            <span>Total: <strong className="font-mono">{formatCedis(summary.total_collected)}</strong></span>
            <span>{summary.contribution_count} contributions · {summary.contributor_count} contributors</span>
          </div>
        )}

        <form onSubmit={submit} className="mt-4 rounded-sm bg-white p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Record a contribution</p>
          <div className="mt-2 grid grid-cols-2 gap-3">
            <div className="col-span-2">
              {memberId ? (
                <div className="flex items-center justify-between rounded-sm border border-[var(--rule)] px-3 py-2 text-sm">
                  <span>{memberName}</span>
                  <button type="button" onClick={() => { setMemberId(""); setQuery(""); }} className="text-xs text-[var(--clay-red)]">Change</button>
                </div>
              ) : (
                <>
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search a family member…"
                    className="w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
                  />
                  {memberResults && memberResults.length > 0 && (
                    <ul className="mt-1 max-h-28 divide-y divide-[var(--rule)] overflow-y-auto rounded-sm border border-[var(--rule)]">
                      {memberResults.map((m) => (
                        <li key={m.id}>
                          <button
                            type="button"
                            onClick={() => { setMemberId(m.id); setMemberName(m.full_name); }}
                            className="w-full px-3 py-1.5 text-left text-sm hover:bg-[var(--surface)]"
                          >
                            {m.full_name}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </>
              )}
            </div>
            <input
              type="number" min="0.01" step="0.01" value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="Any amount"
              className="rounded-sm border border-[var(--rule)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value as FundPaymentMethod)}
              className="rounded-sm border border-[var(--rule)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            >
              <option value="cash">Cash</option>
              <option value="mobile_money">Mobile Money</option>
              <option value="bank">Bank</option>
              <option value="other">Other</option>
            </select>
          </div>
          {contribute.isError && <p className="mt-2 text-sm text-[var(--clay-red)]">{contribute.error.message}</p>}
          <button
            type="submit"
            disabled={contribute.isPending || !memberId || !amount}
            className="mt-3 rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {contribute.isPending ? "Recording…" : "Record & issue receipt"}
          </button>
        </form>

        <div className="mt-4 overflow-hidden rounded-sm border border-[var(--rule)]">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--rule)] text-left text-xs uppercase tracking-wide text-[var(--ink-soft)]">
                <th className="px-3 py-2">Member</th>
                <th className="px-3 py-2">Method</th>
                <th className="px-3 py-2">Receipt</th>
                <th className="px-3 py-2 text-right">Amount</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {contributions?.length === 0 && (
                <tr><td colSpan={5} className="px-3 py-4 text-center text-[var(--ink-soft)]">No contributions yet.</td></tr>
              )}
              {contributions?.map((c) => (
                <tr key={c.id} className="border-b border-[var(--rule)] last:border-b-0">
                  <td className="px-3 py-2 font-medium">{c.member_name}</td>
                  <td className="px-3 py-2 text-[var(--ink-soft)]">{c.payment_method}</td>
                  <td className="px-3 py-2 font-mono text-xs text-[var(--ink-soft)]">{c.receipt_number}</td>
                  <td className="px-3 py-2 text-right font-mono">{formatCedis(c.amount)}</td>
                  <td className="px-3 py-2 text-right">
                    <button onClick={() => viewReceipt(c.id)} className="text-xs text-[var(--forest)] hover:underline">
                      Receipt
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function AssignOfficerPanel({ familyId, family }: { familyId: string; family?: import("@/types/family").Family }) {
  const assignOfficer = useAssignFamilyOfficer(familyId);
  const [query, setQuery] = useState("");
  const [role, setRole] = useState<"secretary" | "treasurer">("secretary");

  const { data: memberResults } = useQuery({
    queryKey: ["officer-assignment-search", query],
    queryFn: () => membersApi.list({ search: query }),
    enabled: query.trim().length >= 2,
  });

  return (
    <div className="mb-6 rounded-sm bg-[var(--surface)] p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">
        Delegate — assign a family secretary or treasurer
      </p>
      <p className="mt-1 text-xs text-[var(--ink-soft)]">
        Currently: Secretary — {family?.family_secretary?.full_name ?? "not assigned"} · Treasurer — {family?.family_treasurer?.full_name ?? "not assigned"}.
        They get access to this page immediately, with no change to their regular login role.
      </p>
      <div className="mt-2 flex items-center gap-2">
        <select
          value={role}
          onChange={(e) => setRole(e.target.value as "secretary" | "treasurer")}
          className="rounded-sm border border-[var(--rule)] bg-white px-2 py-1.5 text-sm"
        >
          <option value="secretary">Secretary</option>
          <option value="treasurer">Treasurer</option>
        </select>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search a family member to assign…"
          className="flex-1 rounded-sm border border-[var(--rule)] bg-white px-3 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
        />
      </div>
      {memberResults && memberResults.length > 0 && (
        <ul className="mt-2 max-h-28 divide-y divide-[var(--rule)] overflow-y-auto rounded-sm bg-white">
          {memberResults.map((m) => (
            <li key={m.id} className="flex items-center justify-between px-3 py-1.5 text-sm">
              <span>{m.full_name}</span>
              <button
                onClick={() => assignOfficer.mutate({ memberId: m.id, officerRole: role }, { onSuccess: () => setQuery("") })}
                disabled={assignOfficer.isPending}
                className="rounded-sm border border-[var(--rule)] px-2 py-1 text-xs font-medium hover:border-[var(--forest)] hover:text-[var(--forest)]"
              >
                Assign as {role}
              </button>
            </li>
          ))}
        </ul>
      )}
      {assignOfficer.isError && <p className="mt-1 text-xs text-[var(--clay-red)]">{assignOfficer.error.message}</p>}
    </div>
  );
}

function FamilyOfficerPositionsPanel({ familyId, isFamilyHead }: { familyId: string; isFamilyHead: boolean }) {
  const { data: positions, isLoading } = useFamilyOfficerPositions(familyId);
  const appoint = useAppointFamilyOfficerPosition(familyId);
  const remove = useRemoveFamilyOfficerPosition(familyId);

  const [query, setQuery] = useState("");
  const [title, setTitle] = useState(SUGGESTED_FAMILY_OFFICER_TITLES[0]);
  const [customTitle, setCustomTitle] = useState("");
  const usingCustomTitle = title === "__custom__";

  const { data: memberResults } = useQuery({
    queryKey: ["officer-position-search", query],
    queryFn: () => membersApi.list({ search: query }),
    enabled: isFamilyHead && query.trim().length >= 2,
  });

  return (
    <div className="mb-6 rounded-sm bg-[var(--surface)] p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">
        Family executive positions
      </p>
      <p className="mt-1 text-xs text-[var(--ink-soft)]">
        Organizational recognition, not a login role — an appointee&apos;s account and permissions
        never change because of a position recorded here. Visible to the whole community.
      </p>

      {isLoading && <p className="mt-2 text-xs text-[var(--ink-soft)]">Loading…</p>}
      {positions && positions.length === 0 && <p className="mt-2 text-xs text-[var(--ink-soft)]">No positions recorded yet.</p>}
      {positions && positions.length > 0 && (
        <ul className="mt-2 divide-y divide-[var(--rule)] rounded-sm bg-white">
          {positions.map((p) => (
            <li key={p.id} className="flex items-center justify-between px-3 py-2 text-sm">
              <span>
                <span className="font-medium">{p.title}</span> — {p.member_name}
              </span>
              {isFamilyHead && (
                <button
                  onClick={() => remove.mutate(p.id)}
                  disabled={remove.isPending}
                  className="text-xs text-[var(--clay-red)] hover:underline"
                >
                  Remove
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {isFamilyHead && (
        <div className="mt-3 border-t border-[var(--rule)] pt-3">
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="rounded-sm border border-[var(--rule)] bg-white px-2 py-1.5 text-sm"
            >
              {SUGGESTED_FAMILY_OFFICER_TITLES.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
              <option value="__custom__">Other — custom title…</option>
            </select>
            {usingCustomTitle && (
              <input
                value={customTitle}
                onChange={(e) => setCustomTitle(e.target.value)}
                placeholder="Custom title"
                className="rounded-sm border border-[var(--rule)] bg-white px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
              />
            )}
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search a family member to appoint…"
              className="flex-1 rounded-sm border border-[var(--rule)] bg-white px-3 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
            />
          </div>
          {memberResults && memberResults.length > 0 && (
            <ul className="mt-2 max-h-28 divide-y divide-[var(--rule)] overflow-y-auto rounded-sm bg-white">
              {memberResults.map((m) => (
                <li key={m.id} className="flex items-center justify-between px-3 py-1.5 text-sm">
                  <span>{m.full_name}</span>
                  <button
                    onClick={() => {
                      const finalTitle = usingCustomTitle ? customTitle.trim() : title;
                      if (!finalTitle) return;
                      appoint.mutate({ memberId: m.id, title: finalTitle }, { onSuccess: () => { setQuery(""); setCustomTitle(""); } });
                    }}
                    disabled={appoint.isPending || (usingCustomTitle && !customTitle.trim())}
                    className="rounded-sm border border-[var(--rule)] px-2 py-1 text-xs font-medium hover:border-[var(--forest)] hover:text-[var(--forest)] disabled:opacity-50"
                  >
                    Appoint
                  </button>
                </li>
              ))}
            </ul>
          )}
          {appoint.isError && <p className="mt-1 text-xs text-[var(--clay-red)]">{appoint.error.message}</p>}
        </div>
      )}
    </div>
  );
}

function FuneralExpensesPanel({ familyId }: { familyId: string }) {
  const { data: families } = useFamilies(false);
  const family = families?.find((f) => f.id === familyId);
  const user = useAuthStore((s) => s.user);

  const { data: allFunerals } = useFunerals("all");
  const familyFunerals = allFunerals?.filter((f) => f.deceased_family === familyId) ?? [];
  const [funeralId, setFuneralId] = useState("");

  const { data: expenses, isLoading, isError } = useFuneralExpenses(familyId, funeralId || undefined);
  const { data: summary } = useExpenditureSummary(familyId, funeralId || undefined);
  const recordExpense = useRecordFuneralExpense(familyId);
  const decide = useDecideFuneralExpense(familyId);
  const [showRecord, setShowRecord] = useState(false);

  // The family's own treasurer OR the family head (the abusuapanin has
  // ultimate authority over his own family's affairs) — matches the
  // backend's is_family_finance_officer check exactly. This governs
  // who can approve/reject.
  const isFinanceOfficer = Boolean(
    user?.is_superuser
    || (user?.linked_member_id && family?.family_treasurer?.id === user.linked_member_id)
    || (user?.linked_member_id && family?.family_head?.id === user.linked_member_id)
  );
  // "The family head is not allowed to purchase any items, his own is
  // to review, reject or approve items bought." Recording a purchase
  // is deliberately narrower — Secretary/Treasurer, never the Head.
  const isFamilyHead = Boolean(user?.linked_member_id && family?.family_head?.id === user.linked_member_id);
  const canRecord = !isFamilyHead;

  return (
    <section className="mt-8 rounded-sm border border-[var(--rule)] bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-[var(--ink-soft)]">
            Every purchase — date, item, seller, amount, who paid
          </p>
          <h2 className="font-display mt-1 text-xl">Funeral Expenses</h2>
          <p className="mt-1 max-w-xl text-sm text-[var(--ink-soft)]">
            Family Secretary or Treasurer records each purchase — the abusuapanin never
            purchases directly, only reviews. Approval or rejection belongs to this
            family's own Treasurer, or the abusuapanin himself.
          </p>
        </div>
        <div className="flex shrink-0 gap-2">
          {funeralId && (
            <button
              onClick={async () => {
                const res = await authFetch(`/families/${familyId}/funeral-expenses/summary/?funeral_event=${funeralId}&export=pdf`);
                if (!res.ok) return;
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                window.open(url, "_blank");
                setTimeout(() => URL.revokeObjectURL(url), 30_000);
              }}
              className="flex items-center rounded-sm border border-[var(--rule)] px-4 py-2 text-sm font-medium hover:border-[var(--ink)]"
            >
              Download PDF
            </button>
          )}
          {canRecord && (
            <button
              onClick={() => setShowRecord(true)}
              disabled={!funeralId}
              className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            >
              Record a purchase
            </button>
          )}
        </div>
      </div>

      <select
        value={funeralId}
        onChange={(e) => setFuneralId(e.target.value)}
        className="mt-3 w-full max-w-sm rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
      >
        <option value="">Choose this family's funeral…</option>
        {familyFunerals.map((f) => (
          <option key={f.id} value={f.id}>{f.deceased_name}</option>
        ))}
      </select>

      {!funeralId && (
        <p className="mt-3 text-sm text-[var(--ink-soft)]">Choose a funeral above to see and record its expenses.</p>
      )}

      {funeralId && (
        <>
          {isError && (
            <div className="mt-4 rounded-sm border border-dashed border-[var(--clay-red)] p-4 text-center text-sm text-[var(--clay-red)]">
              Not permitted to view this family's expenses.
            </div>
          )}

          {summary && (
            <div className="mt-4 grid grid-cols-3 gap-3 rounded-sm bg-[var(--surface)] p-3 text-center text-sm">
              <div>
                <p className="text-xs text-[var(--gold)]">Pending</p>
                <p className="font-mono text-lg font-medium">{formatCedis(summary.pending.total)}</p>
                <p className="text-xs text-[var(--ink-soft)]">{summary.pending.count} item(s)</p>
              </div>
              <div>
                <p className="text-xs text-[var(--forest)]">Approved</p>
                <p className="font-mono text-lg font-medium">{formatCedis(summary.approved.total)}</p>
                <p className="text-xs text-[var(--ink-soft)]">{summary.approved.count} item(s)</p>
              </div>
              <div>
                <p className="text-xs text-[var(--clay-red)]">Rejected</p>
                <p className="font-mono text-lg font-medium">{formatCedis(summary.rejected.total)}</p>
                <p className="text-xs text-[var(--ink-soft)]">{summary.rejected.count} item(s)</p>
              </div>
            </div>
          )}

          <div className="mt-4 overflow-hidden rounded-sm border border-[var(--rule)]">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--rule)] text-left text-xs uppercase tracking-wide text-[var(--ink-soft)]">
                  <th className="px-3 py-2">Item</th>
                  <th className="px-3 py-2">Seller</th>
                  <th className="px-3 py-2">Date</th>
                  <th className="px-3 py-2">Paid by</th>
                  <th className="px-3 py-2 text-right">Amount</th>
                  <th className="px-3 py-2">Status</th>
                  {isFinanceOfficer && <th className="px-3 py-2"></th>}
                </tr>
              </thead>
              <tbody>
                {isLoading && <tr><td colSpan={7} className="px-3 py-4 text-center text-[var(--ink-soft)]">Loading…</td></tr>}
                {expenses?.length === 0 && <tr><td colSpan={7} className="px-3 py-4 text-center text-[var(--ink-soft)]">No expenses recorded yet.</td></tr>}
                {expenses?.map((e) => (
                  <tr key={e.id} className="border-b border-[var(--rule)] last:border-b-0">
                    <td className="px-3 py-2 font-medium">{e.item_name}</td>
                    <td className="px-3 py-2 text-[var(--ink-soft)]">
                      {e.seller_name}
                      {e.seller_contact && <span className="block text-xs">{e.seller_contact}</span>}
                    </td>
                    <td className="px-3 py-2 text-xs text-[var(--ink-soft)]">{e.date_purchased}</td>
                    <td className="px-3 py-2 text-[var(--ink-soft)]">{e.paid_by_member_name ?? "—"}</td>
                    <td className="px-3 py-2 text-right font-mono">{formatCedis(e.amount)}</td>
                    <td className="px-3 py-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        e.status === "approved" ? "bg-[var(--forest-soft)] text-[var(--forest)]"
                        : e.status === "rejected" ? "bg-[var(--clay-red-soft)] text-[var(--clay-red)]"
                        : "bg-[var(--gold-soft)] text-[var(--gold)]"
                      }`}>
                        {e.status}
                      </span>
                      {e.status === "rejected" && e.rejection_reason && (
                        <p className="mt-0.5 text-xs text-[var(--ink-soft)]">{e.rejection_reason}</p>
                      )}
                      {e.status === "approved" && (
                        <PrintReceiptButton
                          getText={() => familyFuneralExpensesApi.voucherText(familyId, e.id)}
                          label="View voucher"
                          className="mt-0.5 block text-xs text-[var(--forest)] hover:underline"
                        />
                      )}
                    </td>
                    {isFinanceOfficer && (
                      <td className="px-3 py-2 text-right">
                        {e.status === "pending" && (
                          <div className="flex justify-end gap-1">
                            <button
                              onClick={() => decide.mutate({ expenseId: e.id, action: "approve" })}
                              className="rounded-sm border border-[var(--forest)] px-2 py-1 text-xs font-medium text-[var(--forest)]"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => {
                                const reason = window.prompt("Reason for rejecting (optional):") ?? "";
                                decide.mutate({ expenseId: e.id, action: "reject", reason });
                              }}
                              className="rounded-sm border border-[var(--clay-red)] px-2 py-1 text-xs font-medium text-[var(--clay-red)]"
                            >
                              Reject
                            </button>
                          </div>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {showRecord && funeralId && (
        <RecordExpenseDialog
          familyId={familyId}
          funeralId={funeralId}
          onClose={() => setShowRecord(false)}
          onRecord={recordExpense}
        />
      )}
    </section>
  );
}

function RecordExpenseDialog({
  familyId, funeralId, onClose, onRecord,
}: {
  familyId: string; funeralId: string; onClose: () => void;
  onRecord: ReturnType<typeof useRecordFuneralExpense>;
}) {
  const [itemName, setItemName] = useState("");
  const [sellerName, setSellerName] = useState("");
  const [sellerContact, setSellerContact] = useState("");
  const [amount, setAmount] = useState("");
  const [datePurchased, setDatePurchased] = useState(() => new Date().toISOString().slice(0, 10));
  const [query, setQuery] = useState("");
  const [paidById, setPaidById] = useState("");
  const [paidByName, setPaidByName] = useState("");

  const { data: memberResults } = useQuery({
    queryKey: ["expense-payer-search", query],
    queryFn: () => membersApi.list({ search: query }),
    enabled: query.trim().length >= 2 && !paidById,
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!itemName.trim() || !sellerName.trim() || !amount || !datePurchased) return;
    onRecord.mutate(
      {
        funeral_event: funeralId, item_name: itemName.trim(), seller_name: sellerName.trim(),
        seller_contact: sellerContact || undefined, amount, date_purchased: datePurchased,
        paid_by_member_id: paidById || undefined,
      },
      { onSuccess: onClose }
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="font-body w-full max-w-sm rounded-sm bg-[var(--surface)] p-6 text-[var(--ink)] shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <h2 className="font-display text-xl">Record a purchase</h2>
          <button onClick={onClose} className="text-[var(--ink-soft)] hover:text-[var(--ink)]" aria-label="Close">✕</button>
        </div>
        <form onSubmit={submit} className="mt-4 space-y-3">
          <div>
            <label className="text-sm font-medium">Item</label>
            <input value={itemName} onChange={(e) => setItemName(e.target.value)} placeholder="e.g. Coffin"
              className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium">Seller</label>
              <input value={sellerName} onChange={(e) => setSellerName(e.target.value)}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]" />
            </div>
            <div>
              <label className="text-sm font-medium">Seller contact</label>
              <input value={sellerContact} onChange={(e) => setSellerContact(e.target.value)}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium">Amount</label>
              <input type="number" min="0.01" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]" />
            </div>
            <div>
              <label className="text-sm font-medium">Date purchased</label>
              <input type="date" value={datePurchased} onChange={(e) => setDatePurchased(e.target.value)}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]" />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium">Who paid (optional)</label>
            {paidById ? (
              <div className="mt-1 flex items-center justify-between rounded-sm border border-[var(--rule)] px-3 py-2 text-sm">
                <span>{paidByName}</span>
                <button type="button" onClick={() => { setPaidById(""); setQuery(""); }} className="text-xs text-[var(--clay-red)]">Change</button>
              </div>
            ) : (
              <>
                <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search a family member…"
                  className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]" />
                {memberResults && memberResults.length > 0 && (
                  <ul className="mt-1 max-h-28 divide-y divide-[var(--rule)] overflow-y-auto rounded-sm border border-[var(--rule)]">
                    {memberResults.map((m) => (
                      <li key={m.id}>
                        <button type="button" onClick={() => { setPaidById(m.id); setPaidByName(m.full_name); }}
                          className="w-full px-3 py-1.5 text-left text-sm hover:bg-white">
                          {m.full_name}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </div>
          {onRecord.isError && <p className="text-sm text-[var(--clay-red)]">{onRecord.error.message}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-3 py-2 text-sm text-[var(--ink-soft)]">Cancel</button>
            <button type="submit" disabled={onRecord.isPending} className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
              {onRecord.isPending ? "Recording…" : "Record purchase"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function FamilyFinancialOverviewCard({ familyId }: { familyId: string }) {
  const { data: overview, isError } = useFamilyFinancialOverview(familyId);
  if (isError || !overview) return null;

  const netIsPositive = Number(overview.net_position) >= 0;

  return (
    <div className="mb-6 rounded-sm border-2 border-[var(--forest)] bg-white p-4">
      <p className="font-mono text-[11px] font-medium uppercase tracking-[0.16em] text-[var(--forest)]">
        The abusuapanin's overview — everything at a glance
      </p>
      <div className="mt-2 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div>
          <p className="text-xs text-[var(--ink-soft)]">Fund contributions</p>
          <p className="font-mono text-lg font-semibold">{formatCedis(overview.total_fund_contributions)}</p>
        </div>
        <div>
          <p className="text-xs text-[var(--ink-soft)]">Approved spend</p>
          <p className="font-mono text-lg font-semibold">{formatCedis(overview.total_approved_expenses)}</p>
        </div>
        <div>
          <p className="text-xs text-[var(--gold)]">Awaiting approval</p>
          <p className="font-mono text-lg font-semibold">{formatCedis(overview.total_pending_expenses)}</p>
        </div>
        <div>
          <p className="text-xs text-[var(--ink-soft)]">Net position</p>
          <p className={`font-mono text-lg font-semibold ${netIsPositive ? "text-[var(--forest)]" : "text-[var(--clay-red)]"}`}>
            {formatCedis(overview.net_position)}
          </p>
        </div>
      </div>
    </div>
  );
}
