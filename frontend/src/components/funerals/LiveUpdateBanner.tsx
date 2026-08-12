"use client";

import { useEffect, useState } from "react";
import type { LedgerEvent } from "@/lib/hooks/useFuneralLiveUpdates";
import { formatCedis } from "@/lib/formatCedis";

export function LiveUpdateBanner({ connected, lastEvent }: { connected: boolean; lastEvent: LedgerEvent | null }) {
  const [visibleEvent, setVisibleEvent] = useState<LedgerEvent | null>(null);

  useEffect(() => {
    if (!lastEvent) return;
    setVisibleEvent(lastEvent);
    const timeout = setTimeout(() => setVisibleEvent(null), 6000);
    return () => clearTimeout(timeout);
  }, [lastEvent]);

  return (
    <div className="flex items-center gap-3">
      <span className="flex items-center gap-1.5 text-xs text-[var(--ink-soft)]">
        <span
          aria-hidden
          className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-[var(--forest)]" : "bg-[var(--clay-red)]"}`}
        />
        {connected ? "Live" : "Reconnecting…"}
      </span>
      {visibleEvent?.event === "payment_recorded" && (
        <span className="rounded-full bg-[var(--forest-soft)] px-3 py-1 text-xs font-medium text-[var(--forest)]">
          {visibleEvent.member_name} just paid {formatCedis(visibleEvent.amount ?? "0")}
        </span>
      )}
    </div>
  );
}
