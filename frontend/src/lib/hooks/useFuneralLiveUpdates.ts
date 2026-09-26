import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";

export interface LedgerEvent {
  event: string;
  member_name?: string;
  amount?: string;
  new_balance?: string;
  payment_status?: string;
}

function wsUrl(funeralId: string, accessToken: string | null): string {
  const base = process.env.NEXT_PUBLIC_API_URL ?? "";
  const wsBase = base.replace(/^https/, "wss").replace(/^http/, "ws");
  const tokenParam = accessToken ? `?token=${encodeURIComponent(accessToken)}` : "";
  return `${wsBase}/ws/funerals/${funeralId}/${tokenParam}`;
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
 * The browser's own WebSocket API cannot set a custom Authorization
 * header, so the same access token already used for every REST
 * request is sent as a query parameter instead, and validated on the
 * backend before the connection is ever accepted (see
 * realtime/consumers.py) — a funeral's own memorial page is public
 * and carries this same id in its URL, so this genuinely has to be
 * checked, not left open.
 */
export function useFuneralLiveUpdates(funeralId: string) {
  const queryClient = useQueryClient();
  const accessToken = useAuthStore((s) => s.accessToken);
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<LedgerEvent | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!funeralId || !accessToken) return;
    let cancelled = false;
    let reconnectTimer: ReturnType<typeof setTimeout>;

    function connect() {
      if (cancelled) return;
      const socket = new WebSocket(wsUrl(funeralId, accessToken));
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
  }, [funeralId, accessToken, queryClient]);

  return { connected, lastEvent };
}
