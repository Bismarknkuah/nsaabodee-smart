"use client";

import "@/styles/family-registry-tokens.css";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { membersApi } from "@/lib/api/members";
import { aiApi } from "@/lib/api/aiFeatures";
import { reportsApi } from "@/lib/api/reports";
import { funeralsApi } from "@/lib/api/funerals";
import { useMemberOutstandingObligations } from "@/lib/hooks/useReports";
import { PayViaMomoDialog } from "@/components/funerals/PayViaMomoDialog";
import { formatCedis } from "@/lib/formatCedis";
import { openReceiptPrintWindow } from "@/lib/openReceiptPrintWindow";
import { enqueueOperation, newClientOpId } from "@/lib/offlineQueue";
import { cacheMembers, cacheObligations, getCachedObligations, searchCachedMembers, type CachedObligation } from "@/lib/offlineCache";
import { useOnlineStatus } from "@/lib/hooks/useOnlineStatus";
import { useOfflineSync } from "@/lib/hooks/useOfflineSync";
import type { PaymentMethod } from "@/types/funeral";

/**
 * "Can also visit the desk at the funeral grounds to make payment
 * there." A cashier standing at a physical front desk doesn't want to
 * navigate Families → Funerals → the full committee ledger to find one
 * person's row — this is a single-purpose page: search a member, see
 * exactly what they owe right now, take the payment (cash, MoMo, or
 * anything else), print the receipt, done. Every underlying call here
 * (search, the obligations list, recording a payment) is the same
 * tested backend endpoint every other screen already uses — this page
 * is just a faster path to them.
 *
 * "Once the person logs in online, the desk officers should be able to
 * work and later synchronize" — every live search and every live
 * obligations lookup silently warms a local cache (see
 * lib/offlineCache.ts) the moment it succeeds. If the connection drops
 * mid-shift, this page keeps working off whatever it already saw —
 * clearly labeled as cached, never presented as if it were live.
 */
export default function FrontDeskPage() {
  const [query, setQuery] = useState("");
  const [selectedMemberId, setSelectedMemberId] = useState<string | null>(null);
  const [selectedMemberName, setSelectedMemberName] = useState<string>("");
  const { online, pendingCount, syncing } = useOfflineSync();

  const { data: exactResults } = useQuery({
    queryKey: ["front-desk-search", query],
    queryFn: async () => {
      const results = await membersApi.list({ search: query });
      cacheMembers(results.map((m) => ({ id: m.id, full_name: m.full_name, membership_number: m.membership_number })));
      return results;
    },
    enabled: query.trim().length >= 2 && online,
  });
  const { data: fuzzyResults } = useQuery({
    queryKey: ["front-desk-fuzzy-search", query],
    queryFn: () => aiApi.search(query),
    enabled: query.trim().length >= 2 && online && (exactResults?.length ?? 0) === 0,
  });
  const { data: cachedResults } = useQuery({
    queryKey: ["front-desk-cached-search", query],
    queryFn: () => searchCachedMembers(query),
    enabled: query.trim().length >= 2 && !online,
  });

  const showingCached = !online;
  const results = showingCached ? cachedResults : exactResults;

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Front Desk</p>
            <h1 className="font-display mt-1 text-4xl">Take a Payment</h1>
          </div>
          <div className="flex items-center gap-1.5 border border-[var(--rule)] px-3 py-1.5 font-mono text-xs">
            <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${online ? "bg-[var(--forest)]" : "bg-[var(--clay-red)]"}`} />
            {online ? (syncing ? "Syncing…" : "Online") : `Offline${pendingCount > 0 ? ` — ${pendingCount} saved on this device` : ""}`}
          </div>
        </div>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Search the person standing in front of you, see what they currently owe, and record
          the payment — cash, MoMo, or otherwise. No signal? Cash payments still save on this
          device and sync automatically the moment you&apos;re back online, and search/balances
          fall back to whatever this device last saw while it was connected.
        </p>
      </header>

      <main className="px-8 py-8">
        {!selectedMemberId ? (
          <div className="mx-auto max-w-lg">
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by name, phone, or membership number…"
              className="w-full rounded-sm border border-[var(--rule)] bg-white px-4 py-3 text-base outline-none focus:border-[var(--forest)]"
            />
            {showingCached && query.trim().length >= 2 && (
              <p className="mt-2 text-xs text-[var(--gold)]">
                Offline — searching only people this device has seen before, not the full roster.
              </p>
            )}
            <ul className="mt-3 divide-y divide-[var(--rule)] rounded-sm border border-[var(--rule)] bg-white">
              {results?.map((m) => (
                <li key={m.id}>
                  <button
                    onClick={() => { setSelectedMemberId(m.id); setSelectedMemberName(m.full_name); }}
                    className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-[var(--surface)]"
                  >
                    <span>{m.full_name}</span>
                    <span className="font-mono text-xs text-[var(--ink-soft)]">{m.membership_number}</span>
                  </button>
                </li>
              ))}
              {!showingCached && exactResults?.length === 0 && fuzzyResults && fuzzyResults.length > 0 && (
                <>
                  <li className="px-4 py-2 text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">
                    No exact match — did you mean
                  </li>
                  {fuzzyResults.map((m) => (
                    <li key={m.member_id}>
                      <button
                        onClick={() => { setSelectedMemberId(m.member_id); setSelectedMemberName(m.full_name); }}
                        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-[var(--surface)]"
                      >
                        <span>{m.full_name}</span>
                        <span className="font-mono text-xs text-[var(--ink-soft)]">{m.membership_number}</span>
                      </button>
                    </li>
                  ))}
                </>
              )}
            </ul>
            <p className="mt-4 text-center text-sm text-[var(--ink-soft)]">
              Not a registered member? Go to the funeral&apos;s own page and use{" "}
              <span className="font-medium">Record a gift</span> instead — guests don&apos;t
              have a mandatory obligation to look up here.
            </p>
          </div>
        ) : (
          <FrontDeskMemberPanel
            memberId={selectedMemberId}
            memberName={selectedMemberName}
            online={online}
            onBack={() => { setSelectedMemberId(null); setQuery(""); }}
          />
        )}
      </main>
    </div>
  );
}

function FrontDeskMemberPanel({ memberId, memberName, online, onBack }: { memberId: string; memberName: string; online: boolean; onBack: () => void }) {
  const { data: liveObligations, isLoading, isSuccess } = useMemberOutstandingObligations(online ? memberId : null);
  const [cachedObligations, setCachedObligations] = useState<CachedObligation[] | null>(null);
  const [momoFor, setMomoFor] = useState<string | null>(null);
  const [cashFor, setCashFor] = useState<string | null>(null);

  // Warm the cache the instant a live lookup succeeds.
  useEffect(() => {
    if (isSuccess && liveObligations) {
      cacheObligations(memberId, liveObligations.map((o) => ({
        obligation_id: o.obligation_id, funeral_id: o.funeral_id, deceased_name: o.deceased_name,
        rate_type: o.rate_type, balance: o.balance, payment_status: o.payment_status,
      })));
    }
  }, [isSuccess, liveObligations, memberId]);

  // Offline: fall back to whatever was last cached for this member.
  useEffect(() => {
    if (!online) {
      getCachedObligations(memberId).then(setCachedObligations).catch(() => setCachedObligations([]));
    }
  }, [online, memberId]);

  const obligations = online ? liveObligations : cachedObligations ?? undefined;
  const cacheTimestamp = !online && cachedObligations && cachedObligations.length > 0 ? cachedObligations[0].cachedAt : null;

  return (
    <div className="mx-auto max-w-2xl">
      <button onClick={onBack} className="text-sm text-[var(--forest)] hover:underline">← Search again</button>
      <h2 className="font-display mt-2 text-2xl">{memberName}</h2>

      {!online && (
        <p className="mt-1 text-xs text-[var(--gold)]">
          Offline{cacheTimestamp ? ` — showing what this device saw as of ${new Date(cacheTimestamp).toLocaleTimeString()}` : " — nothing cached for this person yet"}
        </p>
      )}

      {online && isLoading && <p className="mt-4 text-sm text-[var(--ink-soft)]">Loading what they owe…</p>}

      {obligations?.length === 0 && (
        <div className="mt-6 rounded-sm border border-dashed border-[var(--rule)] p-6 text-center">
          <p className="font-display text-lg" style={{ color: "var(--forest)" }}>Nothing owed right now</p>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">No outstanding balance on any active funeral.</p>
        </div>
      )}

      <ul className="mt-4 space-y-3">
        {obligations?.map((o) => (
          <li key={o.obligation_id} className="rounded-sm border border-[var(--rule)] bg-white p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">{o.deceased_name}</p>
                <p className="text-xs text-[var(--ink-soft)]">
                  {o.rate_type === "own_family" ? "Family Ledger" : "Community Ledger"} · owes {formatCedis(o.balance)}
                </p>
              </div>
              <div className="flex gap-2">
                {online && (
                  <button
                    onClick={() => setMomoFor(o.obligation_id)}
                    className="rounded-sm px-3 py-1.5 text-xs font-medium text-white"
                    style={{ backgroundColor: "var(--gold)" }}
                  >
                    MoMo
                  </button>
                )}
                <button
                  onClick={() => setCashFor(o.obligation_id)}
                  className="rounded-sm border border-[var(--rule)] px-3 py-1.5 text-xs font-medium hover:border-[var(--forest)] hover:text-[var(--forest)]"
                >
                  Cash / Other
                </button>
              </div>
            </div>
            {cashFor === o.obligation_id && (
              <QuickCashForm
                funeralId={o.funeral_id}
                obligationId={o.obligation_id}
                balance={o.balance}
                memberName={memberName}
                onDone={() => setCashFor(null)}
              />
            )}
          </li>
        ))}
      </ul>

      {momoFor && liveObligations && (
        <PayViaMomoDialog
          obligationId={momoFor}
          balance={liveObligations.find((o) => o.obligation_id === momoFor)?.balance ?? "0"}
          label={memberName}
          onClose={() => setMomoFor(null)}
        />
      )}
    </div>
  );
}

function QuickCashForm({
  funeralId, obligationId, balance, memberName, onDone,
}: { funeralId: string; obligationId: string; balance: string; memberName: string; onDone: () => void }) {
  const qc = useQueryClient();
  const online = useOnlineStatus();
  const [amount, setAmount] = useState(balance);
  const [method, setMethod] = useState<PaymentMethod>("cash");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [queuedOffline, setQueuedOffline] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    const clientOpId = newClientOpId();

    if (!online) {
      // "The system should be both online and offline, as some
      // communities have bad networks." Queued locally with the exact
      // same client_op_id the server would have required anyway — once
      // connectivity returns, this syncs automatically (see
      // useOfflineSync) through the identical record-payment call an
      // online submission would have made, debt-priority check and all.
      try {
        await enqueueOperation({
          id: clientOpId, type: "payment", funeralId, obligationId,
          payload: { amount, method, client_op_id: clientOpId },
          label: `${memberName} — ${formatCedis(amount)} (${method})`,
          createdAt: new Date().toISOString(),
        });
        setQueuedOffline(true);
        setTimeout(onDone, 1200);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not save this offline — try again.");
      } finally {
        setIsSaving(false);
      }
      return;
    }

    try {
      const payment = await funeralsApi.recordPayment(funeralId, obligationId, { amount, method, client_op_id: clientOpId });
      qc.invalidateQueries({ queryKey: ["member-outstanding-obligations"] });
      if (method === "cash") {
        const text = await reportsApi.contributionReceiptText(payment.id);
        openReceiptPrintWindow(text);
      }
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not record this payment.");
    } finally {
      setIsSaving(false);
    }
  };

  if (queuedOffline) {
    return (
      <p className="mt-3 border-t border-[var(--rule)] pt-3 text-sm text-[var(--gold)]">
        Saved on this device — will sync automatically once you&apos;re back online.
      </p>
    );
  }

  return (
    <form onSubmit={submit} className="mt-3 flex items-end gap-2 border-t border-[var(--rule)] pt-3">
      {!online && (
        <p className="w-full text-xs text-[var(--gold)]">
          No connection right now — this will be saved on this device and synced automatically later.
        </p>
      )}
      <div>
        <label className="text-xs text-[var(--ink-soft)]">Amount</label>
        <input
          type="number" min="0.01" step="0.01" value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="mt-1 w-28 rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
        />
      </div>
      <div>
        <label className="text-xs text-[var(--ink-soft)]">Method</label>
        <select
          value={method}
          onChange={(e) => setMethod(e.target.value as PaymentMethod)}
          className="mt-1 rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
        >
          <option value="cash">Cash</option>
          <option value="bank">Bank</option>
          <option value="other">Other</option>
        </select>
      </div>
      <button
        type="submit"
        disabled={isSaving}
        className="rounded-sm bg-[var(--forest)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60"
      >
        {isSaving ? "Recording…" : "Record"}
      </button>
      <button type="button" onClick={onDone} className="text-sm text-[var(--ink-soft)]">Cancel</button>
      {error && <p className="w-full text-xs text-[var(--clay-red)]">{error}</p>}
    </form>
  );
}
