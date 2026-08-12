import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

export interface LedgerEvent {
  event: string;
  member_name?: string;
  amount?: string;
  new_balance?: string;
  payment_status?: string;
}

function wsUrl(funeralId: string): string {
  const base = process.env.NEXT_PUBLIC_API_URL ?? "";
  const wsBase = base.replace(/^https/, "wss").replace(/^http/, "ws");
  return `${wsBase}/ws/funerals/${funeralId}/`;
}

/**
 * Live updates for a single funeral's ledger — a payment recorded on
 * another device shows up here without a manual refresh (see the
 * backend's realtime/consumers.py). Reconnects automatically on drop
 * (a phone losing signal briefly shouldn't need a page reload to
 * resume live updates), and degrades silently if the connection never
 * opens at all — this is a nice-to-have, not something the page's core
 * functionality (which still works via ordinary polling/refetch)
 * should ever depend on.
 *
 * No auth token is sent on this connection — the backend consumer
 * doesn't check one yet either (a real, flagged gap on the backend
 * side), so this matches what's actually enforced today rather than
 * pretending to a security property that doesn't exist yet.
 */
export function useFuneralLiveUpdates(funeralId: string) {
  const queryClient = useQueryClient();
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<LedgerEvent | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!funeralId) return;
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      if (cancelled) return;
      const socket = new WebSocket(wsUrl(funeralId));
      socketRef.current = socket;

      socket.onopen = () => setConnected(true);
      socket.onclose = () => {
        setConnected(false);
        if (!cancelled) reconnectTimer = setTimeout(connect, 3000);
      };
      socket.onerror = () => socket.close();
      socket.onmessage = (event) => {
        try {
          const data: LedgerEvent = JSON.parse(event.data);
          setLastEvent(data);
          if (data.event === "payment_recorded") {
            queryClient.invalidateQueries({ queryKey: ["funeral-obligations", funeralId] });
            queryClient.invalidateQueries({ queryKey: ["funeral-summary", funeralId] });
          }
        } catch {
          // Ignore anything that isn't the JSON shape we expect.
        }
      };
    }

    connect();
    return () => {
      cancelled = true;
      clearTimeout(reconnectTimer);
      socketRef.current?.close();
    };
  }, [funeralId, queryClient]);

  return { connected, lastEvent };
}
