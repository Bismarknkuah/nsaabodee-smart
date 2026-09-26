"use client";

import "@/styles/family-registry-tokens.css";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { membersApi, arrearsApi } from "@/lib/api/members";
import { aiApi } from "@/lib/api/aiFeatures";
import { reportsApi } from "@/lib/api/reports";
import { funeralsApi } from "@/lib/api/funerals";
import { useMemberOutstandingObligations } from "@/lib/hooks/useReports";
import { useRecordPaymentsAcrossActiveFunerals } from "@/lib/hooks/useFunerals";
import { useRouter, useSearchParams } from "next/navigation";
import { formatCedis } from "@/lib/formatCedis";
import { openReceiptPrintWindow } from "@/lib/openReceiptPrintWindow";
import { isBluetoothPrintingSupported, printReceiptViaBluetooth } from "@/lib/bluetoothPrinter";
import { QrScannerModal, isQrScanningSupported, extractMemberIdFromScan } from "@/components/QrScannerModal";
import { enqueueOperation, newClientOpId } from "@/lib/offlineQueue";
import { cacheMembers, cacheObligations, getCachedObligations, searchCachedMembers, type CachedObligation } from "@/lib/offlineCache";
import { useOnlineStatus } from "@/lib/hooks/useOnlineStatus";
import { useOfflineSync } from "@/lib/hooks/useOfflineSync";
import { useDeskSession, type DeskSession } from "@/lib/hooks/useDeskSession";
import { useAuthStore } from "@/store/authStore";
import type { PaymentMethod } from "@/types/funeral";
import type { OutstandingObligation } from "@/types/reports";

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
/**
 * "Once paid, printing should be so easier and should support either
 * connecting printer by Bluetooth, wireless, or cable." One shared
 * place both payment forms below call into, so the printer connection
 * chosen once at desk-opening time (see OpenDeskForm) is what actually
 * gets used — never silently falling back to the plain system-print
 * path regardless of what the collector picked.
 */
async function printReceiptWithSessionMethod(paymentId: string, text: string, printMethod: DeskSession["printMethod"]) {
  // "The receipt should have a bar scan code so that they can scan to
  // confirm their payment." A failure fetching the QR code should
  // never block the receipt itself from printing — the text is what
  // actually matters; the scan code is an enhancement on top of it.
  const qrCode = await reportsApi.contributionReceiptQrCode(paymentId).catch(() => null);
  if (printMethod === "bluetooth") {
    await printReceiptViaBluetooth(text, qrCode?.verify_url);
  } else {
    openReceiptPrintWindow(text, qrCode?.qr_code_base64);
  }
}

export default function FrontDeskPage() {
  const searchParams = useSearchParams();
  const [query, setQuery] = useState(() => searchParams.get("q") ?? "");
  const [selectedMemberId, setSelectedMemberId] = useState<string | null>(null);
  const [selectedMemberName, setSelectedMemberName] = useState<string>("");
  const [scannerOpen, setScannerOpen] = useState(false);
  const [scanError, setScanError] = useState<string | null>(null);
  const { online, pendingCount, syncing, drainQueue, refreshQueue } = useOfflineSync();
  const { session, setSession, clearSession, hydrated } = useDeskSession();
  const currentUser = useAuthStore((s) => s.user);
  const qrScanningSupported = isQrScanningSupported();

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

  // "So before any collector clicks open desk, the person has to fill
  // some forms to select either to print receipt or send SMS, type
  // his name." Nothing on this page is usable until this is set once.
  if (!hydrated) return null;
  if (!session) {
    return <OpenDeskForm defaultName={currentUser?.username ?? ""} onOpen={setSession} />;
  }

  return (
    <div className="font-body min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="border-b border-[var(--border)] bg-[var(--card)] px-8 py-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--text-soft)]">Front Desk</p>
            <h1 className="font-display mt-1 text-4xl">Take a Payment</h1>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 border border-[var(--border)] px-3 py-1.5 font-mono text-xs">
              <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${online ? "bg-[var(--forest)]" : "bg-[var(--clay-red)]"}`} />
              {online ? (syncing ? "Syncing…" : "Online") : `Offline${pendingCount > 0 ? ` — ${pendingCount} saved on this device` : ""}`}
            </div>
            {/*
              "I want the synchronize and refresh to be like this
              template, so that all the collectors and data entries
              can be done when the network is unavailable and later
              can be synchronized when the network is restored." A
              collector working through a bad connection shouldn't
              have to leave this page and visit Pending Sync just to
              force a retry — the exact same drainQueue this page
              already runs automatically the instant connectivity
              returns, just also reachable by hand, right here.
            */}
            <button
              onClick={() => refreshQueue()}
              className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium hover:border-[var(--forest)]"
            >
              Refresh
            </button>
            <button
              onClick={() => drainQueue()}
              disabled={!online || syncing || pendingCount === 0}
              className="rounded-lg bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
            >
              {syncing ? "Syncing…" : "Sync now"}
            </button>
          </div>
        </div>
        <div className="mt-2 flex items-center gap-3 text-xs text-[var(--text-soft)]">
          <span>
            Collecting as <span className="font-medium text-[var(--text)]">{session.collectorName}</span>, delivering by{" "}
            <span className="font-medium text-[var(--text)]">{session.deliveryMethod === "sms" ? "SMS" : "printed receipt"}</span>
          </span>
          <button onClick={clearSession} className="underline">Change</button>
        </div>
        <p className="mt-2 max-w-2xl text-sm text-[var(--text-soft)]">
          Search the person standing in front of you, see what they currently owe, and record
          the payment — cash, MoMo, or otherwise. No signal? Cash payments still save on this
          device and sync automatically the moment you&apos;re back online, and search/balances
          fall back to whatever this device last saw while it was connected.
        </p>
      </header>

      <main className="px-8 py-8">
        {!selectedMemberId ? (
          <div className="mx-auto max-w-lg">
            <ActiveFuneralsSummary />
            <div className="flex gap-2">
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by name, phone, or membership number…"
                className="flex-1 rounded-lg border border-[var(--border)] bg-white px-4 py-3 text-base outline-none focus:border-[var(--forest)]"
              />
              {qrScanningSupported && (
                <button
                  type="button"
                  onClick={() => setScannerOpen(true)}
                  className="shrink-0 rounded-lg border border-[var(--border)] px-3 text-sm font-medium hover:border-[var(--forest)]"
                >
                  Scan
                </button>
              )}
            </div>
            {scanError && <p className="mt-2 text-xs text-[var(--clay-red)]">{scanError}</p>}
            {scannerOpen && (
              <QrScannerModal
                onClose={() => setScannerOpen(false)}
                onDetected={(rawValue) => {
                  setScannerOpen(false);
                  const memberId = extractMemberIdFromScan(rawValue);
                  if (!memberId) {
                    setScanError("That QR code isn't a Nsaabodeɛ Smart membership card.");
                    return;
                  }
                  setScanError(null);
                  membersApi.get(memberId).then(
                    (member) => { setSelectedMemberId(member.id); setSelectedMemberName(member.full_name); },
                    () => setScanError("Couldn't find a member for that card.")
                  );
                }}
              />
            )}
            {showingCached && query.trim().length >= 2 && (
              <p className="mt-2 text-xs text-[var(--gold)]">
                Offline — searching only people this device has seen before, not the full roster.
              </p>
            )}
            <ul className="mt-3 divide-y divide-[var(--border-soft)] rounded-lg border border-[var(--border)] bg-white">
              {results?.map((m) => (
                <li key={m.id}>
                  <button
                    onClick={() => { setSelectedMemberId(m.id); setSelectedMemberName(m.full_name); }}
                    className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-[var(--bg)]"
                  >
                    <span>{m.full_name}</span>
                    <span className="font-mono text-xs text-[var(--text-soft)]">{m.membership_number}</span>
                  </button>
                </li>
              ))}
              {!showingCached && exactResults?.length === 0 && fuzzyResults && fuzzyResults.length > 0 && (
                <>
                  <li className="px-4 py-2 text-xs font-medium uppercase tracking-wide text-[var(--text-soft)]">
                    No exact match — did you mean
                  </li>
                  {fuzzyResults.map((m) => (
                    <li key={m.member_id}>
                      <button
                        onClick={() => { setSelectedMemberId(m.member_id); setSelectedMemberName(m.full_name); }}
                        className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-[var(--bg)]"
                      >
                        <span>{m.full_name}</span>
                        <span className="font-mono text-xs text-[var(--text-soft)]">{m.membership_number}</span>
                      </button>
                    </li>
                  ))}
                </>
              )}
            </ul>
            <p className="mt-4 text-center text-sm text-[var(--text-soft)]">
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
            deskSession={session}
            onBack={() => { setSelectedMemberId(null); setQuery(""); }}
          />
        )}
      </main>
    </div>
  );
}

/**
 * "So before any collector clicks open desk, the person has to fill
 * some forms to select either to print receipt or send SMS, type his
 * name, so that he doesn't have to type his name for all the
 * payment." A one-time setup, not a per-payment form. Once submitted,
 * every payment recorded in this session reuses this name and
 * delivery choice automatically.
 */
/**
 * "The community collector should see all available ongoing funerals
 * opened to collect payment." Collapsed by default since most desk
 * work is just searching a person, not browsing funerals, but always
 * one click away.
 */
function ActiveFuneralsSummary() {
  const [open, setOpen] = useState(false);
  const { data: funerals, isLoading } = useQuery({
    queryKey: ["front-desk-active-funerals"],
    queryFn: () => funeralsApi.list("active"),
    enabled: open,
  });

  return (
    <div className="mb-4 rounded-lg border border-[var(--border)] bg-white">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-4 py-2.5 text-left text-sm font-medium"
      >
        <span>Funerals currently open for collection</span>
        <span className="text-[var(--text-soft)]">{open ? "Hide" : "Show"}</span>
      </button>
      {open && (
        <div className="border-t border-[var(--border)]">
          {isLoading && <p className="px-4 py-3 text-sm text-[var(--text-soft)]">Loading…</p>}
          {funerals?.length === 0 && <p className="px-4 py-3 text-sm text-[var(--text-soft)]">No funerals are currently open.</p>}
          <ul className="divide-y divide-[var(--border-soft)]">
            {funerals?.map((f) => (
              <li key={f.id} className="px-4 py-2.5 text-sm">
                {f.deceased_name}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}


/**
 * "So before any collector clicks open desk, the person has to fill
 * some forms to select either to print receipt or send SMS, type his
 * name, so that he doesn't have to type his name for all the
 * payment." A one-time setup, not a per-payment form. Once submitted,
 * every payment recorded in this session reuses this name and
 * delivery choice automatically.
 */
function OpenDeskForm({ defaultName, onOpen }: { defaultName: string; onOpen: (session: DeskSession) => void }) {
  const [name, setName] = useState(defaultName);
  const [deliveryMethod, setDeliveryMethod] = useState<DeskSession["deliveryMethod"]>("print");
  const [printMethod, setPrintMethod] = useState<DeskSession["printMethod"]>("system");
  const bluetoothAvailable = isBluetoothPrintingSupported();

  return (
    <div className="font-body flex min-h-screen items-center justify-center bg-[var(--bg)] text-[var(--text)]">
      <form
        onSubmit={(e) => { e.preventDefault(); if (name.trim()) onOpen({ collectorName: name.trim(), deliveryMethod, printMethod }); }}
        className="w-full max-w-sm rounded-lg border border-[var(--border)] bg-white p-6"
      >
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--text-soft)]">Front Desk</p>
        <h1 className="font-display mt-1 text-2xl">Open desk</h1>
        <p className="mt-2 text-sm text-[var(--text-soft)]">
          Set this once for your shift. You will not be asked again until you choose
          to change it.
        </p>

        <div className="mt-4">
          <label className="text-sm font-medium">Your name</label>
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Who is collecting today?"
            className="mt-1 w-full rounded-lg border border-[var(--border)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
          />
        </div>

        <div className="mt-4">
          <label className="text-sm font-medium">How should the payer get their receipt?</label>
          <div className="mt-2 space-y-2">
            <label className="flex items-center gap-2 text-sm">
              <input type="radio" name="delivery" checked={deliveryMethod === "print"} onChange={() => setDeliveryMethod("print")} />
              Print a receipt
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input type="radio" name="delivery" checked={deliveryMethod === "sms"} onChange={() => setDeliveryMethod("sms")} />
              Send an SMS with a tracking link
            </label>
          </div>
        </div>

        {/*
          "Once paid, printing should be so easier and should support
          either connecting printer by Bluetooth, wireless, or cable."
          Chosen once here, not re-offered after every payment — a
          Bluetooth printer only needs picking once per shift anyway
          (bluetoothPrinter.ts caches the connected device for the
          rest of the session).
        */}
        {deliveryMethod === "print" && (
          <div className="mt-4">
            <label className="text-sm font-medium">How is the printer connected?</label>
            <div className="mt-2 space-y-2">
              <label className="flex items-center gap-2 text-sm">
                <input type="radio" name="printer" checked={printMethod === "system"} onChange={() => setPrintMethod("system")} />
                Cable or wireless (already set up as a system printer)
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input
                  type="radio" name="printer" checked={printMethod === "bluetooth"} onChange={() => setPrintMethod("bluetooth")}
                  disabled={!bluetoothAvailable}
                />
                Bluetooth {!bluetoothAvailable && "(needs Chrome or Edge)"}
              </label>
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={!name.trim()}
          className="mt-6 w-full rounded-lg bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          Open desk
        </button>
      </form>
    </div>
  );
}

function FrontDeskMemberPanel({ memberId, memberName, online, deskSession, onBack }: { memberId: string; memberName: string; online: boolean; deskSession: DeskSession; onBack: () => void }) {
  const { data: liveObligations, isLoading, isSuccess } = useMemberOutstandingObligations(online ? memberId : null);
  const router = useRouter();
  const [cachedObligations, setCachedObligations] = useState<CachedObligation[] | null>(null);
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
      <button
        onClick={onBack}
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-sm font-medium text-[var(--text)] hover:border-[var(--primary)] hover:text-[var(--primary)]"
      >
        ← Search again
      </button>
      <h2 className="font-display mt-3 text-2xl">{memberName}</h2>

      {!online && (
        <p className="mt-1 text-xs text-[var(--gold)]">
          Offline{cacheTimestamp ? ` — showing what this device saw as of ${new Date(cacheTimestamp).toLocaleTimeString()}` : " — nothing cached for this person yet"}
        </p>
      )}

      {online && isLoading && <p className="mt-4 text-sm text-[var(--text-soft)]">Loading what they owe…</p>}

      {obligations?.length === 0 && (
        <div className="mt-6 rounded-[var(--radius)] border border-dashed border-[var(--border)] bg-[var(--card)] p-8 text-center">
          <p className="text-2xl font-semibold" style={{ color: "var(--forest)" }}>Nothing owed right now</p>
          <p className="mt-1 text-sm text-[var(--text-soft)]">No outstanding balance on any active funeral.</p>
        </div>
      )}

      {liveObligations && liveObligations.length > 1 && online && (
        <PayAllPanel memberId={memberId} memberName={memberName} obligations={liveObligations} deskSession={deskSession} />
      )}

      <ul className="mt-4 space-y-3">
        {obligations?.map((o) => (
          <li key={o.obligation_id} className="rounded-[var(--radius)] bg-[var(--card)] p-5" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-base font-medium">{o.deceased_name}</p>
                <p className="text-xs uppercase tracking-wide text-[var(--text-soft)]">
                  {o.rate_type === "own_family" ? "Family Ledger" : "Community Ledger"}
                </p>
                {/* The amount owed is the single most important number on this card — sized and colored to be read at a glance, not buried in a caption line. */}
                <p className="mt-1 text-2xl font-semibold" style={{ color: "var(--clay-red)" }}>{formatCedis(o.balance)}</p>
              </div>
              <div className="flex gap-2">
                {online && (
                  <button
                    onClick={() => router.push(`/pay-momo/${o.obligation_id}?balance=${o.balance}&label=${encodeURIComponent(memberName)}`)}
                    className="rounded-lg px-4 py-2.5 text-sm font-semibold text-white transition-colors"
                    style={{ backgroundColor: "var(--gold)" }}
                  >
                    MoMo
                  </button>
                )}
                <button
                  onClick={() => setCashFor(o.obligation_id)}
                  className="rounded-lg bg-[var(--forest)] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[var(--forest-hover)]"
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
                deskSession={deskSession}
                onDone={() => setCashFor(null)}
              />
            )}
          </li>
        ))}
      </ul>

      {online && <ArrearsSection memberId={memberId} memberName={memberName} deskSession={deskSession} />}
    </div>
  );
}

/**
 * "When the person standing in front of the table mentions their
 * name or code, their arrears they own should show." Deliberately
 * separate from the active-funeral obligations list above it, since
 * this covers closed funerals too, the genuine arrears case, not
 * duplicating what is already shown for active ones.
 */
function ArrearsSection({ memberId, memberName, deskSession }: { memberId: string; memberName: string; deskSession: DeskSession }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["member-arrears", memberId], queryFn: () => arrearsApi.lookup(memberId) });
  const [payingId, setPayingId] = useState<string | null>(null);
  const [correctingId, setCorrectingId] = useState<string | null>(null);

  const closedArrears = data?.arrears.filter((a) => a.funeral_status !== "active") ?? [];
  const role = useAuthStore((s) => s.user?.role);
  // "Differentiate the arrears officers and the contribution collectors."
  // A plain Collector collects on open funerals only — arrears are the
  // Arrears Collector's work, so here they get a referral, not a form.
  const canCollectArrears = role !== "collector";

  if (isLoading) return null;
  if (closedArrears.length === 0) return null;

  if (!canCollectArrears) {
    const total = closedArrears.reduce((sum, a) => sum + Number(a.balance), 0);
    return (
      <div className="mt-6 rounded-[var(--radius)] p-5" style={{ backgroundColor: "var(--clay-red-soft)", border: "1px solid color-mix(in srgb, var(--clay-red) 25%, transparent)" }}>
        <h3 className="text-lg font-semibold" style={{ color: "var(--clay-red)" }}>Arrears from past funerals — refer to the Arrears Collector</h3>
        <p className="mt-1 text-sm">
          {memberName.split(" ")[0]} owes <strong>{formatCedis(String(total))}</strong> across {closedArrears.length} closed funeral{closedArrears.length === 1 ? "" : "s"}.
          Arrears must be cleared before the current bill can be paid, and they are collected at the Arrears Desk, not here.
        </p>
        <ul className="mt-2 text-xs text-[var(--text-soft)]">
          {closedArrears.map((a) => <li key={a.id}>{a.funeral_deceased_name} — {formatCedis(a.balance)}</li>)}
        </ul>
      </div>
    );
  }

  return (
    <div className="mt-6 rounded-[var(--radius)] p-5" style={{ backgroundColor: "var(--clay-red-soft)", border: "1px solid color-mix(in srgb, var(--clay-red) 25%, transparent)" }}>
      <h3 className="text-lg font-semibold" style={{ color: "var(--clay-red)" }}>Arrears from past funerals</h3>
      <p className="mt-1 text-xs text-[var(--text-soft)]">
        Owed from funerals that have already closed. Must be settled here before {memberName.split(" ")[0]} can be
        marked clear.
      </p>
      <ul className="mt-3 space-y-3">
        {closedArrears.map((a) => (
          <li key={a.id} className="rounded-[var(--radius)] bg-[var(--card)] p-4" style={{ boxShadow: "var(--shadow-sm)" }}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-sm font-medium">{a.funeral_deceased_name}</p>
                <p className="text-xs text-[var(--text-soft)]">
                  {a.funeral_status} funeral, started {new Date(a.funeral_collection_start_date).toLocaleDateString()}
                </p>
                <p className="mt-1 text-xl font-semibold" style={{ color: "var(--clay-red)" }}>{formatCedis(a.balance)}</p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1.5">
                <button
                  onClick={() => { setPayingId(a.id); setCorrectingId(null); }}
                  className="rounded-lg px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--forest-hover)]"
                  style={{ backgroundColor: "var(--forest)" }}
                >
                  Record payment
                </button>
                <button onClick={() => { setCorrectingId(a.id); setPayingId(null); }} className="text-xs font-medium text-[var(--text-soft)] hover:underline">
                  Already paid, not reflected
                </button>
              </div>
            </div>

            {payingId === a.id && (
              <ArrearsPaymentForm
                funeralId={a.funeral_event}
                obligationId={a.id}
                balance={a.balance}
                memberName={memberName}
                deskSession={deskSession}
                onDone={() => { setPayingId(null); qc.invalidateQueries({ queryKey: ["member-arrears", memberId] }); }}
              />
            )}
            {correctingId === a.id && (
              <ArrearsCorrectionForm
                obligationId={a.id}
                balance={a.balance}
                onDone={() => setCorrectingId(null)}
              />
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Same recording path as QuickCashForm, reused for a closed funeral's arrears rather than duplicating the payment logic. */
function ArrearsPaymentForm({ funeralId, obligationId, balance, memberName, deskSession, onDone }: { funeralId: string; obligationId: string; balance: string; memberName: string; deskSession: DeskSession; onDone: () => void }) {
  const [amount, setAmount] = useState(balance);
  const [method, setMethod] = useState<PaymentMethod>("cash");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recordedAmount, setRecordedAmount] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    try {
      const payment = await funeralsApi.recordPayment(funeralId, obligationId, {
        amount, method, client_op_id: newClientOpId(), collector_name: deskSession.collectorName,
      });
      if (method === "cash") {
        if (deskSession.deliveryMethod === "sms") {
          await reportsApi.sendPaymentTrackingSms(payment.id).catch(() => undefined);
        } else {
          const text = await reportsApi.contributionReceiptText(payment.id);
          await printReceiptWithSessionMethod(payment.id, text, deskSession.printMethod);
        }
      }
      setRecordedAmount(amount);
      setTimeout(onDone, 1100);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not record this payment.");
    } finally {
      setIsSaving(false);
    }
  };

  if (recordedAmount) {
    return (
      <div className="mt-2 flex items-center gap-2 border-t border-[var(--border)] pt-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-white" style={{ backgroundColor: "var(--forest)" }}>✓</span>
        <p className="text-sm font-semibold" style={{ color: "var(--forest)" }}>{formatCedis(recordedAmount)} recorded</p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="mt-2 flex items-end gap-2 border-t border-[var(--border)] pt-2">
      <div>
        <label className="text-xs text-[var(--text-soft)]">Amount</label>
        <input
          type="number" min="0.01" step="0.01" value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="mt-1 w-28 rounded-lg border border-[var(--border)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
        />
      </div>
      <div>
        <label className="text-xs text-[var(--text-soft)]">Method</label>
        <select
          value={method}
          onChange={(e) => setMethod(e.target.value as PaymentMethod)}
          className="mt-1 rounded-lg border border-[var(--border)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
        >
          <option value="cash">Cash</option>
          <option value="bank">Bank</option>
          <option value="other">Other</option>
        </select>
      </div>
      <button type="submit" disabled={isSaving} className="rounded-lg bg-[var(--forest)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--forest-hover)] disabled:opacity-60">
        {isSaving ? "Recording…" : "Record"}
      </button>
      {error && <p className="w-full text-xs text-[var(--clay-red)]">{error}</p>}
    </form>
  );
}

/**
 * "If they paid but the system didn't reflect, the arrears collector
 * should edit but have to be approved by the community treasurer
 * before it reflects." This form only ever creates the REQUEST,
 * nothing here changes the balance until a Treasurer decides it.
 */
function ArrearsCorrectionForm({ obligationId, balance, onDone }: { obligationId: string; balance: string; onDone: () => void }) {
  const [amount, setAmount] = useState(balance);
  const [method, setMethod] = useState<PaymentMethod>("cash");
  const [reason, setReason] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!reason.trim()) return;
    setIsSaving(true);
    setError(null);
    try {
      await funeralsApi.requestArrearsCorrection(obligationId, { amount, method, reason: reason.trim() });
      setSubmitted(true);
      setTimeout(onDone, 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit this correction request.");
    } finally {
      setIsSaving(false);
    }
  };

  if (submitted) {
    return (
      <p className="mt-2 border-t border-[var(--border)] pt-2 text-xs" style={{ color: "var(--forest)" }}>
        Sent to the Community Treasurer for approval. Nothing changes here until it is decided.
      </p>
    );
  }

  return (
    <form onSubmit={submit} className="mt-2 space-y-2 border-t border-[var(--border)] pt-2">
      <p className="text-xs text-[var(--text-soft)]">
        This does not settle the balance yet. It only asks the Community Treasurer to review and approve it.
      </p>
      <div className="flex gap-2">
        <input
          type="number" min="0.01" step="0.01" value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="w-28 rounded-lg border border-[var(--border)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
        />
        <select
          value={method}
          onChange={(e) => setMethod(e.target.value as PaymentMethod)}
          className="rounded-lg border border-[var(--border)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
        >
          <option value="cash">Cash</option>
          <option value="bank">Bank</option>
          <option value="other">Other</option>
        </select>
      </div>
      <textarea
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Why was this never reflected? (e.g. a handwritten receipt from the time)"
        rows={2}
        className="w-full rounded-lg border border-[var(--border)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
      />
      <button type="submit" disabled={isSaving || !reason.trim()} className="rounded-lg bg-[var(--forest)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60">
        {isSaving ? "Sending…" : "Send for Treasurer approval"}
      </button>
      {error && <p className="text-xs text-[var(--clay-red)]">{error}</p>}
    </form>
  );
}

function QuickCashForm({
  funeralId, obligationId, balance, memberName, deskSession, onDone,
}: { funeralId: string; obligationId: string; balance: string; memberName: string; deskSession: DeskSession; onDone: () => void }) {
  const qc = useQueryClient();
  const online = useOnlineStatus();
  const [amount, setAmount] = useState(balance);
  const [method, setMethod] = useState<PaymentMethod>("cash");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [queuedOffline, setQueuedOffline] = useState(false);
  const [smsResult, setSmsResult] = useState<string | null>(null);
  // "Make it easy and user friendly" — a payment recorded online with
  // no SMS delivery used to call onDone() immediately, so the form
  // just silently vanished with no confirmation at all. A collector
  // handling cash needs to see, unmistakably, that the amount was
  // actually recorded before moving to the next person.
  const [recordedAmount, setRecordedAmount] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setError(null);
    const clientOpId = newClientOpId();

    if (!online) {
      // "The system should be both online and offline, as some
      // communities have bad networks." Queued locally with the exact
      // same client_op_id the server would have required anyway, once
      // connectivity returns, this syncs automatically (see
      // useOfflineSync) through the identical record-payment call an
      // online submission would have made, debt-priority check and all.
      try {
        await enqueueOperation({
          id: clientOpId, type: "payment", funeralId, obligationId,
          payload: { amount, method, client_op_id: clientOpId, collector_name: deskSession.collectorName },
          label: `${memberName} — ${formatCedis(amount)} (${method})`,
          createdAt: new Date().toISOString(),
        });
        setQueuedOffline(true);
        setTimeout(onDone, 1200);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not save this offline. Try again.");
      } finally {
        setIsSaving(false);
      }
      return;
    }

    try {
      const payment = await funeralsApi.recordPayment(funeralId, obligationId, { amount, method, client_op_id: clientOpId, collector_name: deskSession.collectorName });
      qc.invalidateQueries({ queryKey: ["member-outstanding-obligations"] });
      if (method === "cash") {
        if (deskSession.deliveryMethod === "sms") {
          try {
            await reportsApi.sendPaymentTrackingSms(payment.id);
            setSmsResult("Tracking SMS sent.");
          } catch (smsErr) {
            setSmsResult(smsErr instanceof Error ? smsErr.message : "Could not send the SMS.");
          }
        } else {
          try {
            const text = await reportsApi.contributionReceiptText(payment.id);
            await printReceiptWithSessionMethod(payment.id, text, deskSession.printMethod);
          } catch (printErr) {
            // The payment itself already succeeded — a printer connection
            // failure here shouldn't read as if the payment failed too.
            setSmsResult(printErr instanceof Error ? `Payment recorded, but printing failed: ${printErr.message}` : "Payment recorded, but printing failed.");
          }
        }
      }
      setRecordedAmount(amount);
      setTimeout(onDone, deskSession.deliveryMethod === "sms" && method === "cash" ? 1500 : 1100);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not record this payment.");
    } finally {
      setIsSaving(false);
    }
  };

  if (recordedAmount) {
    return (
      <div className="mt-3 flex items-center gap-2 rounded-lg border-t-0 pt-3" style={{ borderTop: "1px solid var(--border)" }}>
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-white" style={{ backgroundColor: "var(--forest)" }}>✓</span>
        <p className="text-sm font-semibold" style={{ color: "var(--forest)" }}>
          {formatCedis(recordedAmount)} recorded{smsResult ? ` — ${smsResult}` : deskSession.deliveryMethod === "print" ? ", printing…" : ""}
        </p>
      </div>
    );
  }

  if (queuedOffline) {
    return (
      <p className="mt-3 border-t border-[var(--border)] pt-3 text-sm text-[var(--gold)]">
        Saved on this device — will sync automatically once you&apos;re back online.
      </p>
    );
  }

  return (
    <form onSubmit={submit} className="mt-3 flex items-end gap-2 border-t border-[var(--border)] pt-3">
      {!online && (
        <p className="w-full text-xs text-[var(--gold)]">
          No connection right now — this will be saved on this device and synced automatically later.
        </p>
      )}
      <div>
        <label className="text-xs text-[var(--text-soft)]">Amount</label>
        <input
          type="number" min="0.01" step="0.01" value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="mt-1 w-28 rounded-lg border border-[var(--border)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
        />
      </div>
      <div>
        <label className="text-xs text-[var(--text-soft)]">Method</label>
        <select
          value={method}
          onChange={(e) => setMethod(e.target.value as PaymentMethod)}
          className="mt-1 rounded-lg border border-[var(--border)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
        >
          <option value="cash">Cash</option>
          <option value="bank">Bank</option>
          <option value="other">Other</option>
        </select>
      </div>
      <button
        type="submit"
        disabled={isSaving}
        className="rounded-lg bg-[var(--forest)] px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-[var(--forest-hover)] disabled:opacity-60"
      >
        {isSaving ? "Recording…" : "Record"}
      </button>
      <button type="button" onClick={onDone} className="text-sm text-[var(--text-soft)]">Cancel</button>
      {error && <p className="w-full text-xs text-[var(--clay-red)]">{error}</p>}
      {smsResult && <p className="w-full text-xs" style={{ color: "var(--forest)" }}>{smsResult}</p>}
    </form>
  );
}

/**
 * 'Since it's a community ledger, community members are mandatory to
 * pay all — so the system should be more efficient and friendly, so
 * it can be faster.' One search already surfaces every active
 * funeral's obligation for this member (see FrontDeskMemberPanel
 * above); this is the other half — one form settles every one of them
 * in a single submission, instead of repeating the same Cash/MoMo
 * form once per funeral.
 */
function PayAllPanel({ memberId, memberName, obligations, deskSession }: { memberId: string; memberName: string; obligations: OutstandingObligation[]; deskSession: DeskSession }) {
  const { mutate, isPending, error, isSuccess, data } = useRecordPaymentsAcrossActiveFunerals();
  const [expanded, setExpanded] = useState(false);
  const [method, setMethod] = useState<PaymentMethod>("cash");

  const total = obligations.reduce((sum, o) => sum + Number(o.balance), 0);

  if (isSuccess) {
    return (
      <div className="mb-4 border-2 border-[var(--forest)] bg-white p-4">
        <p className="font-display text-lg" style={{ color: "var(--forest)" }}>
          All {data.length} settled — {formatCedis(total.toString())} total
        </p>
        <p className="mt-1 text-xs text-[var(--text-soft)]">Receipts for each are also available from My Receipts.</p>
      </div>
    );
  }

  return (
    <div className="mb-4 border-2 border-[var(--gold)] bg-white p-4">
      {!expanded ? (
        <button
          onClick={() => setExpanded(true)}
          className="flex w-full items-center justify-between text-left"
        >
          <span className="font-display text-lg">Pay all {obligations.length} at once</span>
          <span className="font-mono text-sm font-medium" style={{ color: "var(--forest)" }}>
            {formatCedis(total.toString())} total →
          </span>
        </button>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutate({ member_id: memberId, method, collector_name: deskSession.collectorName });
          }}
        >
          <p className="font-display text-lg">
            Pay all {obligations.length} — {formatCedis(total.toString())} total
          </p>
          <p className="mt-1 text-xs text-[var(--text-soft)]">
            {memberName}&apos;s full balance across every active funeral, settled in one go.
          </p>
          <div className="mt-3">
            <label className="text-xs font-medium">Method</label>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value as PaymentMethod)}
              className="mt-1 w-full rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            >
              <option value="cash">Cash</option>
              <option value="mobile_money">Mobile Money</option>
              <option value="bank">Bank</option>
              <option value="other">Other</option>
            </select>
          </div>
          {error && <p className="mt-2 text-xs text-[var(--clay-red)]">{error.message}</p>}
          <div className="mt-3 flex justify-end gap-2">
            <button type="button" onClick={() => setExpanded(false)} className="px-3 py-2 text-sm text-[var(--text-soft)]">
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="rounded-lg bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {isPending ? "Recording…" : `Record ${formatCedis(total.toString())}`}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
