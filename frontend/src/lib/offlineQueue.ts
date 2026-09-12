/**
 * "The system should be both online and offline, as some communities
 * have bad networks." The mobile app already has full offline-first
 * architecture (local SQLite + a sync queue, built early in this
 * project) — that remains the right tool for genuinely poor-network
 * environments. This is the honest, SCOPED web counterpart: the one
 * screen where "a desk worker recording money with no signal" actually
 * happens is the Front Desk, so that's what this backs — not a full
 * offline rebuild of the entire web app (no service worker, no asset
 * caching, no general-purpose offline mode for every page).
 *
 * Uses IndexedDB (not localStorage — this needs structured querying and
 * survives far more reliably across browser sessions) to hold operations
 * that couldn't reach the server yet. Every queued operation carries its
 * own `client_op_id`, the exact same idempotency key the backend's
 * record_payment/record_gift_donation already require — so replaying a
 * queued operation after connectivity returns can never double-record
 * a payment even if the request had actually gone through right before
 * the connection dropped.
 */

export type QueuedOperationType = "payment" | "gift";

export interface QueuedOperation {
  id: string; // the client_op_id itself — also the IndexedDB key
  type: QueuedOperationType;
  funeralId: string;
  obligationId?: string; // payments only
  payload: Record<string, unknown>;
  label: string; // human-readable summary for the "pending sync" list
  createdAt: string;
}

const DB_NAME = "nsaabodee_offline_queue";
const DB_VERSION = 1;
const STORE_NAME = "pending_operations";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB isn't available in this browser."));
      return;
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

export async function enqueueOperation(op: QueuedOperation): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    tx.objectStore(STORE_NAME).put(op);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export async function listQueuedOperations(): Promise<QueuedOperation[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readonly");
    const request = tx.objectStore(STORE_NAME).getAll();
    request.onsuccess = () => resolve(request.result as QueuedOperation[]);
    request.onerror = () => reject(request.error);
  });
}

export async function removeQueuedOperation(id: string): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, "readwrite");
    tx.objectStore(STORE_NAME).delete(id);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export function newClientOpId(): string {
  return crypto.randomUUID();
}
