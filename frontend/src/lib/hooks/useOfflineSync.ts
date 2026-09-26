import { useCallback, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { funeralsApi } from "@/lib/api/funerals";
import { giftsApi } from "@/lib/api/gifts";
import { listQueuedOperations, removeQueuedOperation, type QueuedOperation } from "@/lib/offlineQueue";
import { useOnlineStatus } from "./useOnlineStatus";

/**
 * Every queued operation replays through the EXACT same API functions
 * (and therefore the exact same backend idempotency-on-client_op_id
 * guarantee) a live, online submission would have used — there is no
 * separate "offline sync" code path on the backend to keep correct
 * independently. A payment recorded offline, synced an hour later,
 * still goes through the debt-priority check, still triggers the same
 * notifications, still shows up on the member's own dashboard exactly
 * as if it had been typed in live.
 */
async function replay(op: QueuedOperation): Promise<void> {
  if (op.type === "payment" && op.obligationId) {
    await funeralsApi.recordPayment(op.funeralId, op.obligationId, op.payload as Parameters<typeof funeralsApi.recordPayment>[2]);
  } else if (op.type === "gift") {
    await giftsApi.record(op.funeralId, op.payload as Parameters<typeof giftsApi.record>[1]);
  }
}

export function useOfflineSync() {
  const online = useOnlineStatus();
  const qc = useQueryClient();
  const [queuedOperations, setQueuedOperations] = useState<QueuedOperation[]>([]);
  const [syncing, setSyncing] = useState(false);

  const refreshQueue = useCallback(async () => {
    try {
      const ops = await listQueuedOperations();
      setQueuedOperations(ops);
    } catch {
      // IndexedDB unavailable (very old browser, private-browsing
      // restrictions) — the Front Desk still works online-only in that
      // case, it just can't queue anything while offline.
    }
  }, []);

  const drainQueue = useCallback(async () => {
    setSyncing(true);
    try {
      const ops = await listQueuedOperations();
      for (const op of ops) {
        try {
          await replay(op);
          await removeQueuedOperation(op.id);
        } catch {
          // Leave it queued — could be a genuinely failed request (an
          // obligation that's since been fully paid by someone else)
          // or just still offline despite the "online" event firing.
          // Either way, stop draining rather than silently skip ahead
          // out of order. A stuck item can be reviewed and manually
          // discarded from the Pending Sync page (discardOperation
          // below) rather than blocking everything behind it forever.
          break;
        }
      }
      qc.invalidateQueries({ queryKey: ["member-outstanding-obligations"] });
      qc.invalidateQueries({ queryKey: ["gifts"] });
    } finally {
      await refreshQueue();
      setSyncing(false);
    }
  }, [qc, refreshQueue]);

  const discardOperation = useCallback(async (id: string) => {
    await removeQueuedOperation(id);
    await refreshQueue();
  }, [refreshQueue]);

  useEffect(() => {
    refreshQueue();
  }, [refreshQueue]);

  useEffect(() => {
    if (online) drainQueue();
  }, [online, drainQueue]);

  return {
    online,
    pendingCount: queuedOperations.length,
    queuedOperations,
    syncing,
    drainQueue,
    discardOperation,
    refreshQueue,
  };
}
