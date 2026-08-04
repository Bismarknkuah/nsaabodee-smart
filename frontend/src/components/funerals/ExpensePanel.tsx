"use client";

import { useState } from "react";
import { useExpenses, useExpenseSummary, useFuneralLogisticsActions } from "@/lib/hooks/useFuneralLogistics";
import { membersApi } from "@/lib/api/members";
import { useQuery } from "@tanstack/react-query";
import { formatCedis } from "@/lib/formatCedis";
import { useAuthStore } from "@/store/authStore";
import type { ExpenseCategory, ExpenseStatus } from "@/types/funeralLogistics";

const CATEGORY_LABEL: Record<ExpenseCategory, string> = {
  catering: "Catering", transport: "Transport", coffin: "Coffin", venue: "Venue / Canopy / Chairs",
  printing: "Printing", burial_fees: "Burial Fees", other: "Other",
};

const STATUS_LABEL: Record<ExpenseStatus, string> = {
  pending_approval: "Pending Approval", paid: "Paid", partial: "Partially Paid", credit: "Credit (Owed)", cancelled: "Cancelled",
};

const STATUS_ACCENT: Record<ExpenseStatus, string> = {
  pending_approval: "var(--gold)", paid: "var(--forest)", partial: "var(--violet)", credit: "var(--clay-red)", cancelled: "var(--ink-soft)",
};

const CAN_RECORD_EXPENSES = ["community_admin", "treasurer", "financial_secretary"];

export function ExpensePanel({ funeralId }: { funeralId: string }) {
  const { data: expenses, isLoading } = useExpenses(funeralId);
  const { data: summary } = useExpenseSummary(funeralId);
  const { recordExpense, decideExpenseStatus } = useFuneralLogisticsActions(funeralId);
  const [showForm, setShowForm] = useState(false);
  const currentUser = useAuthStore((s) => s.user);
  const canRecord = !!currentUser?.role && CAN_RECORD_EXPENSES.includes(currentUser.role);

  const [description, setDescription] = useState("");
  const [category, setCategory] = useState<ExpenseCategory>("other");
  const [itemName, setItemName] = useState("");
  const [useBreakdown, setUseBreakdown] = useState(false);
  const [quantity, setQuantity] = useState("1");
  const [unitPrice, setUnitPrice] = useState("");
  const [amount, setAmount] = useState("");
  const [supplierName, setSupplierName] = useState("");
  const [buyerQuery, setBuyerQuery] = useState("");
  const [buyerId, setBuyerId] = useState<string | null>(null);
  const [buyerName, setBuyerName] = useState("");
  const [notes, setNotes] = useState("");
  const [incurredOn, setIncurredOn] = useState("");

  const { data: buyerResults } = useQuery({
    queryKey: ["expense-buyer-search", buyerQuery],
    queryFn: () => membersApi.list({ search: buyerQuery }),
    enabled: buyerQuery.trim().length >= 2,
  });

  const reset = () => {
    setDescription(""); setItemName(""); setQuantity("1"); setUnitPrice(""); setAmount("");
    setSupplierName(""); setBuyerId(null); setBuyerName(""); setBuyerQuery(""); setNotes(""); setShowForm(false);
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!description || !incurredOn) return;
    if (useBreakdown ? !quantity || !unitPrice : !amount) return;
    recordExpense.mutate(
      {
        description, category, incurred_on: incurredOn,
        ...(useBreakdown ? { quantity: Number(quantity), unit_price: unitPrice } : { amount }),
        item_name: itemName, supplier_name: supplierName, buyer_id: buyerId ?? undefined, notes,
      },
      { onSuccess: reset }
    );
  };

  return (
    <section className="mt-6 rounded-sm border border-[var(--rule)] bg-white p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-display text-xl">Expenses</h2>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">Money spent on this funeral — catering, transport, coffin, and more.</p>
        </div>
        {canRecord && (
          <button onClick={() => setShowForm((s) => !s)} className="shrink-0 rounded-sm border border-[var(--rule)] px-4 py-2 text-sm font-medium hover:border-[var(--ink)]">
            {showForm ? "Cancel" : "Record expense"}
          </button>
        )}
      </div>

      {summary && summary.expense_count > 0 && (
        <div className="mt-2 flex flex-wrap gap-4 font-mono text-sm">
          <span className="text-[var(--clay-red)]">Total: {formatCedis(summary.total_expenses)}</span>
          {Number(summary.total_owed) > 0 && (
            <span className="text-[var(--gold)]">Still owed: {formatCedis(summary.total_owed)}</span>
          )}
        </div>
      )}

      {summary && Object.keys(summary.by_category).length > 1 && (
        <div className="mt-3 space-y-1.5">
          {Object.entries(summary.by_category)
            .sort(([, a], [, b]) => Number(b) - Number(a))
            .map(([cat, amount]) => {
              const pct = Math.round((Number(amount) / Number(summary.total_expenses)) * 100);
              return (
                <div key={cat} className="flex items-center gap-2 text-xs">
                  <span className="w-28 shrink-0 text-[var(--ink-soft)]">{CATEGORY_LABEL[cat as ExpenseCategory] ?? cat}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-[var(--surface)]">
                    <div className="h-full rounded-full bg-[var(--clay-red)]" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="w-12 shrink-0 text-right font-mono text-[var(--ink-soft)]">{pct}%</span>
                </div>
              );
            })}
        </div>
      )}

      {showForm && canRecord && (
        <form onSubmit={submit} className="mt-4 grid grid-cols-2 gap-3 rounded-sm bg-[var(--surface)] p-3">
          <div className="col-span-2">
            <label className="text-xs font-medium">Description</label>
            <input value={description} onChange={(e) => setDescription(e.target.value)}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm" />
          </div>
          <div>
            <label className="text-xs font-medium">Category</label>
            <select value={category} onChange={(e) => setCategory(e.target.value as ExpenseCategory)}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm">
              {Object.entries(CATEGORY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs font-medium">Item (optional)</label>
            <input value={itemName} onChange={(e) => setItemName(e.target.value)} placeholder="e.g. Plastic chairs"
              className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm" />
          </div>

          <div className="col-span-2 flex items-center gap-2 text-xs">
            <button type="button" onClick={() => setUseBreakdown((v) => !v)} className="text-[var(--forest)] hover:underline">
              {useBreakdown ? "Enter a total amount instead" : "Break down by quantity × unit price instead"}
            </button>
          </div>
          {useBreakdown ? (
            <>
              <div>
                <label className="text-xs font-medium">Quantity</label>
                <input type="number" min="1" value={quantity} onChange={(e) => setQuantity(e.target.value)}
                  className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="text-xs font-medium">Unit price</label>
                <input type="number" min="0.01" step="0.01" value={unitPrice} onChange={(e) => setUnitPrice(e.target.value)}
                  className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm" />
              </div>
            </>
          ) : (
            <div>
              <label className="text-xs font-medium">Amount</label>
              <input type="number" min="0.01" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm" />
            </div>
          )}

          <div>
            <label className="text-xs font-medium">Supplier (optional)</label>
            <input value={supplierName} onChange={(e) => setSupplierName(e.target.value)}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm" />
          </div>
          <div className="relative">
            <label className="text-xs font-medium">Buyer (optional)</label>
            <input
              value={buyerId ? buyerName : buyerQuery}
              onChange={(e) => { setBuyerId(null); setBuyerQuery(e.target.value); }}
              placeholder="Search a member…"
              className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
            />
            {!buyerId && buyerResults && buyerResults.length > 0 && (
              <ul className="absolute z-10 mt-1 max-h-28 w-full overflow-y-auto rounded-sm border border-[var(--rule)] bg-white shadow-sm">
                {buyerResults.map((m) => (
                  <li key={m.id}>
                    <button type="button" onClick={() => { setBuyerId(m.id); setBuyerName(m.full_name); }}
                      className="block w-full px-3 py-1.5 text-left text-sm hover:bg-[var(--surface)]">
                      {m.full_name}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="col-span-2">
            <label className="text-xs font-medium">Notes (optional)</label>
            <input value={notes} onChange={(e) => setNotes(e.target.value)}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm" />
          </div>
          <div className="col-span-2">
            <label className="text-xs font-medium">Date incurred</label>
            <input type="date" value={incurredOn} onChange={(e) => setIncurredOn(e.target.value)}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm" />
          </div>
          {recordExpense.isError && <p className="col-span-2 text-sm text-[var(--clay-red)]">{recordExpense.error.message}</p>}
          <button type="submit" disabled={recordExpense.isPending}
            className="col-span-2 rounded-sm bg-[var(--ink)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
            {recordExpense.isPending ? "Recording…" : "Record expense"}
          </button>
        </form>
      )}

      <ul className="mt-4 divide-y divide-[var(--rule)]">
        {isLoading && <li className="py-3 text-sm text-[var(--ink-soft)]">Loading…</li>}
        {expenses?.map((e) => (
          <li key={e.id} className="py-2 text-sm">
            <div className="flex items-center justify-between">
              <div>
                <p>{e.item_name || e.description}</p>
                <p className="font-mono text-xs text-[var(--ink-soft)]">
                  {CATEGORY_LABEL[e.category]} · {e.voucher_number}
                  {e.supplier_name && ` · ${e.supplier_name}`}
                  {e.buyer_name && ` · bought by ${e.buyer_name}`}
                </p>
              </div>
              <span className="font-mono text-[var(--clay-red)]">−{formatCedis(e.amount)}</span>
            </div>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-[10px] font-medium uppercase tracking-wide" style={{ color: STATUS_ACCENT[e.status] }}>
                {STATUS_LABEL[e.status]}
              </span>
              {Number(e.balance_owed) > 0 && (
                <span className="text-xs text-[var(--gold)]">— {formatCedis(e.balance_owed)} still owed</span>
              )}
              {canRecord && e.status !== "paid" && e.status !== "cancelled" && (
                <select
                  value=""
                  onChange={(ev) => {
                    const value = ev.target.value as ExpenseStatus;
                    if (!value) return;
                    if (value === "partial") {
                      const paid = window.prompt(`How much has been paid so far, out of ${e.amount}?`);
                      if (paid) decideExpenseStatus.mutate({ expenseId: e.id, status: value, amountPaid: paid });
                    } else {
                      decideExpenseStatus.mutate({ expenseId: e.id, status: value });
                    }
                  }}
                  className="ml-auto rounded-sm border border-[var(--rule)] px-2 py-0.5 text-xs"
                >
                  <option value="">Change status…</option>
                  <option value="paid">Mark paid</option>
                  <option value="credit">Mark as credit (owed)</option>
                  <option value="partial">Record partial payment</option>
                  <option value="cancelled">Cancel</option>
                </select>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
