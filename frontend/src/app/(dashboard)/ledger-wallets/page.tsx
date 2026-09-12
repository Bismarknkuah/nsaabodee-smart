"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ledgerWalletsApi, type LedgerWallet } from "@/lib/api/ledgerWallets";
import { formatCedis } from "@/lib/formatCedis";

/**
 * 'Transparent since it's a transaction aspect.' One page, but never
 * the same data twice — the backend's own ledger_wallets_for already
 * decides exactly which wallet(s) an account may see (community-wide
 * for Treasurer, only their own family's for a Family Treasurer, the
 * Town Elders wallet for the Chief), so this page simply renders
 * whatever comes back rather than guessing the role itself.
 */
export default function LedgerWalletsPage() {
  const { data: wallets, isLoading, error } = useQuery({ queryKey: ["ledger-wallets"], queryFn: ledgerWalletsApi.list });
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
          A real, held balance — not just a running total
        </p>
        <h1 className="font-display mt-1 text-4xl">Ledger Wallets</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Every contribution payment credits the matching wallet the moment it's recorded.
          Every withdrawal is its own logged transaction — nothing here is ever a silent balance edit.
        </p>
      </header>

      <main className="px-8 py-8">
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
        {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
        {wallets && wallets.length === 0 && (
          <p className="text-sm text-[var(--ink-soft)]">No wallet exists yet — one is created automatically the first time a matching payment is recorded.</p>
        )}

        <div className="space-y-4">
          {wallets?.map((wallet) => (
            <WalletCard
              key={wallet.id}
              wallet={wallet}
              expanded={expandedId === wallet.id}
              onToggle={() => setExpandedId(expandedId === wallet.id ? null : wallet.id)}
            />
          ))}
        </div>
      </main>
    </div>
  );
}

function WalletCard({ wallet, expanded, onToggle }: { wallet: LedgerWallet; expanded: boolean; onToggle: () => void }) {
  const qc = useQueryClient();
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");

  const { data: transactions } = useQuery({
    queryKey: ["ledger-wallet-transactions", wallet.id],
    queryFn: () => ledgerWalletsApi.transactions(wallet.id),
    enabled: expanded,
  });

  const withdraw = useMutation({
    mutationFn: () => ledgerWalletsApi.withdraw(wallet.id, amount, note),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["ledger-wallets"] });
      qc.invalidateQueries({ queryKey: ["ledger-wallet-transactions", wallet.id] });
      setAmount("");
      setNote("");
    },
  });

  const title = wallet.scope === "own_family" ? `${wallet.family_name}'s Ledger Wallet` : `${wallet.scope_display} Wallet`;

  return (
    <div className="border-2 border-[var(--ink)] bg-white">
      <button onClick={onToggle} className="flex w-full items-center justify-between px-5 py-4 text-left">
        <div>
          <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">{wallet.scope_display}</p>
          <p className="font-display text-xl">{title}</p>
        </div>
        <p className="font-display text-3xl" style={{ color: "var(--forest)" }}>{formatCedis(wallet.balance)}</p>
      </button>

      {expanded && (
        <div className="border-t border-[var(--rule)] px-5 py-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Withdraw</p>
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="number" min="0.01" step="0.01"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              placeholder="Amount"
              className="w-32 rounded-sm border border-[var(--rule)] px-3 py-1.5 text-sm"
            />
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="What this withdrawal is for…"
              className="min-w-[16rem] flex-1 rounded-sm border border-[var(--rule)] px-3 py-1.5 text-sm"
            />
            <button
              onClick={() => withdraw.mutate()}
              disabled={withdraw.isPending || !amount || !note.trim()}
              className="rounded-sm bg-[var(--clay-red)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
            >
              {withdraw.isPending ? "Withdrawing…" : "Withdraw"}
            </button>
          </div>
          {withdraw.isError && <p className="mt-2 text-xs text-[var(--clay-red)]">{withdraw.error.message}</p>}

          <p className="mb-2 mt-5 text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Transaction history</p>
          <ul className="max-h-72 divide-y divide-[var(--rule)] overflow-y-auto border-y border-[var(--rule)]">
            {transactions?.map((t) => (
              <li key={t.id} className="flex items-center justify-between py-2 text-sm">
                <div>
                  <p>{t.note || (t.kind === "credit" ? "Contribution payment" : "Withdrawal")}</p>
                  <p className="text-xs text-[var(--ink-soft)]">
                    {new Date(t.created_at).toLocaleString()}
                    {t.source_payment_receipt && ` · Receipt ${t.source_payment_receipt}`}
                    {t.actor_username && ` · ${t.actor_username}`}
                  </p>
                </div>
                <span className="font-mono font-medium" style={{ color: t.kind === "credit" ? "var(--forest)" : "var(--clay-red)" }}>
                  {t.kind === "credit" ? "+" : "−"}{formatCedis(t.amount)}
                </span>
              </li>
            ))}
            {transactions?.length === 0 && <li className="py-2 text-sm text-[var(--ink-soft)]">No transactions yet.</li>}
          </ul>
        </div>
      )}
    </div>
  );
}
