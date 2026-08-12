"use client";

import "@/styles/family-registry-tokens.css";
import { useOfflineSync } from "@/lib/hooks/useOfflineSync";
import { KpiTile, FolioLink } from "@/components/dashboard/DashboardVisuals";
import { IconWarning, IconMoney } from "@/components/icons/DashboardIcons";

const TYPE_LABEL: Record<string, string> = {
  payment: "Contribution payment",
  gift: "Gift donation",
};

/**
 * "Desk officers should be able to work and later synchronize the data
 * later." Most of the time synchronization is invisible — it just
 * happens the moment connectivity returns. This page exists for the
 * exception: if something stays queued (a genuinely failed request, not
 * just still-offline), a desk officer can see exactly what's stuck, try
 * again on demand, or — if it turns out to have already been recorded
 * some other way — discard it rather than have it silently block every
 * later entry behind it forever.
 */
export default function PendingSyncPage() {
  const { online, queuedOperations, syncing, drainQueue, discardOperation } = useOfflineSync();

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-[var(--ink-soft)]">Front Desk</p>
        <h1 className="font-display mt-1 text-4xl">Pending Sync</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Everything saved on this device while offline, waiting to reach the server. This
          syncs automatically the moment you&apos;re back online — this page is for checking
          in, not something you normally need to manage by hand.
        </p>
      </header>

      <main className="px-8 py-8">
        <div className="grid grid-cols-2 gap-px border border-[var(--rule)] bg-[var(--rule)] sm:max-w-md">
          <KpiTile label={online ? "Status: online" : "Status: offline"} value={online ? "●" : "○"} color={online ? "forest" : "clay"} />
          <KpiTile label="Waiting to sync" value={queuedOperations.length} color={queuedOperations.length > 0 ? "gold" : "forest"} icon={<IconMoney />} />
        </div>

        <div className="mt-6 flex justify-end">
          <button
            onClick={() => drainQueue()}
            disabled={!online || syncing || queuedOperations.length === 0}
            className="bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {syncing ? "Syncing…" : "Sync now"}
          </button>
        </div>

        <div className="mt-4">
          {queuedOperations.length === 0 ? (
            <div className="border border-dashed border-[var(--rule)] px-6 py-10 text-center">
              <p className="font-display text-lg" style={{ color: "var(--forest)" }}>Nothing waiting</p>
              <p className="mt-1 text-sm text-[var(--ink-soft)]">Everything this device has recorded has reached the server.</p>
            </div>
          ) : (
            <ol className="divide-y divide-[var(--rule)] border-y border-[var(--rule)]">
              {queuedOperations.map((op, i) => (
                <li key={op.id} className="flex items-center gap-3 py-3">
                  <span className="font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(2, "0")}</span>
                  <div className="flex-1">
                    <p className="text-sm font-medium">{op.label}</p>
                    <p className="text-xs text-[var(--ink-soft)]">
                      {TYPE_LABEL[op.type] ?? op.type} · saved {new Date(op.createdAt).toLocaleString()}
                    </p>
                  </div>
                  <button onClick={() => discardOperation(op.id)} className="shrink-0 text-xs text-[var(--clay-red)] hover:underline">
                    Discard
                  </button>
                </li>
              ))}
            </ol>
          )}
        </div>

        {!online && queuedOperations.length > 0 && (
          <p className="mt-4 flex items-center gap-1.5 text-xs" style={{ color: "var(--gold)" }}>
            <IconWarning /> Still offline — these will sync automatically once this device reconnects.
          </p>
        )}
      </main>
    </div>
  );
}
