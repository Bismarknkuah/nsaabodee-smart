"use client";

import "@/styles/family-registry-tokens.css";
import Link from "next/link";
import { useMyDonationsReceived } from "@/lib/hooks/useGifts";
import { formatCedis } from "@/lib/formatCedis";

/**
 * "Any amount paid should reflect on the person dashboard... for
 * transparency and accountability." A donation-account holder's own
 * view of every gift recorded in their name, across every funeral —
 * not the community's aggregate gift ledger (which the rest of the
 * funeral committee doesn't see at all), just their own.
 */
export default function MyDonationsReceivedPage() {
  const { data, isLoading, error } = useMyDonationsReceived();

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-xs uppercase tracking-widest" style={{ color: "var(--violet)" }}>
          Ledger 2 — for you specifically
        </p>
        <h1 className="font-display mt-1 text-4xl">Donations Received in My Name</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Every gift anyone has given specifically to you — as a registered donation-account
          holder — across any funeral. This is yours to see regardless of role; nobody else on
          the funeral committee has blanket access to this.
        </p>
      </header>

      <main className="px-8 py-8">
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
        {error && (
          <div className="rounded-sm border border-dashed border-[var(--rule)] p-6 text-center text-sm text-[var(--ink-soft)]">
            {error.message}
          </div>
        )}

        {data && (
          <>
            <div className="mb-6 flex gap-6 rounded-sm p-4" style={{ backgroundColor: "var(--violet-soft)" }}>
              <div>
                <p className="text-xs text-[var(--ink-soft)]">Total received</p>
                <p className="font-mono text-2xl font-semibold" style={{ color: "var(--violet)" }}>
                  {formatCedis(data.total_received)}
                </p>
              </div>
              <div>
                <p className="text-xs text-[var(--ink-soft)]">Donations</p>
                <p className="font-mono text-2xl font-semibold">{data.donation_count}</p>
              </div>
            </div>

            {data.by_funeral.length === 0 ? (
              <div className="rounded-sm border border-dashed border-[var(--rule)] px-6 py-10 text-center">
                <p className="font-display text-lg">Nothing recorded yet</p>
                <p className="mt-1 text-sm text-[var(--ink-soft)]">
                  You&apos;ll need to be registered as a donation-account holder for a
                  specific funeral before gifts can be earmarked to you.
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-[var(--rule)] border-y border-[var(--rule)]">
                {data.by_funeral.map((f) => (
                  <li key={f.funeral_id} className="flex items-center justify-between py-3">
                    <Link href={`/funerals/${f.funeral_id}`} className="hover:text-[var(--forest)] hover:underline">
                      {f.deceased_name}
                    </Link>
                    <div className="text-right">
                      <p className="font-mono font-medium">{formatCedis(f.total_value)}</p>
                      <p className="text-xs text-[var(--ink-soft)]">{f.donation_count} donation{f.donation_count === 1 ? "" : "s"}</p>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </main>
    </div>
  );
}
