/**
 * "Once the person logs in online, the desk officers should be able to
 * work and later synchronize the data" — this is the read side of that:
 * a local cache of whatever the Front Desk last saw while online
 * (the member roster, and each member's own outstanding balances), so
 * going offline mid-shift doesn't mean losing the ability to look
 * someone up and see roughly what they owe. Every cached read is
 * clearly timestamped and surfaced as "as of [time]" wherever it's
 * shown — this is a fallback for continuity, not a claim that offline
 * data is as current as a live lookup.
 *
 * Deliberately a SEPARATE IndexedDB object store from offlineQueue.ts's
 * write queue: this one is disposable, best-effort READ cache (safe to
 * silently overwrite or fall behind); the queue is durable, must-not
 * -lose WRITE data. Keeping them apart means a bug in the cache can
 * never risk losing someone's actual payment.
 */

const DB_NAME = "nsaabodee_offline_cache";
const DB_VERSION = 1;
const MEMBERS_STORE = "cached_members";
const OBLIGATIONS_STORE = "cached_obligations";

export interface CachedMember {
  id: string;
  full_name: string;
  membership_number: string;
  cachedAt: string;
}

export interface CachedObligation {
  member_id: string; // composite lookup key
  obligation_id: string;
  funeral_id: string;
  deceased_name: string;
  rate_type: string;
  balance: string;
  payment_status: string;
  cachedAt: string;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("IndexedDB isn't available in this browser."));
      return;
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(MEMBERS_STORE)) {
        db.createObjectStore(MEMBERS_STORE, { keyPath: "id" });
      }
      if (!db.objectStoreNames.contains(OBLIGATIONS_STORE)) {
        const store = db.createObjectStore(OBLIGATIONS_STORE, { keyPath: "obligation_id" });
        store.createIndex("member_id", "member_id", { unique: false });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/** Called silently every time a live member search succeeds — this is how the cache gets "warmed" while still online. */
export async function cacheMembers(members: { id: string; full_name: string; membership_number: string }[]): Promise<void> {
  try {
    const db = await openDb();
    const tx = db.transaction(MEMBERS_STORE, "readwrite");
    const store = tx.objectStore(MEMBERS_STORE);
    const cachedAt = new Date().toISOString();
    for (const m of members) store.put({ ...m, cachedAt });
  } catch {
    // Caching is best-effort — a failure here should never block the live search that triggered it.
  }
}

export async function searchCachedMembers(query: string): Promise<CachedMember[]> {
  const db = await openDb();
  const all = await new Promise<CachedMember[]>((resolve, reject) => {
    const tx = db.transaction(MEMBERS_STORE, "readonly");
    const request = tx.objectStore(MEMBERS_STORE).getAll();
    request.onsuccess = () => resolve(request.result as CachedMember[]);
    request.onerror = () => reject(request.error);
  });
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return all.filter((m) => m.full_name.toLowerCase().includes(q) || m.membership_number.toLowerCase().includes(q));
}

/** Called silently every time a live obligations lookup succeeds. */
export async function cacheObligations(memberId: string, obligations: Omit<CachedObligation, "member_id" | "cachedAt">[]): Promise<void> {
  try {
    const db = await openDb();
    const tx = db.transaction(OBLIGATIONS_STORE, "readwrite");
    const store = tx.objectStore(OBLIGATIONS_STORE);
    const cachedAt = new Date().toISOString();
    // Clear this member's previously-cached obligations first — an
    // obligation that's since been fully paid (and so no longer appears
    // in a fresh live lookup) shouldn't linger in the cache forever.
    const index = store.index("member_id");
    const existingKeys = await new Promise<IDBValidKey[]>((resolve, reject) => {
      const req = index.getAllKeys(memberId);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
    existingKeys.forEach((key) => store.delete(key));
    for (const o of obligations) store.put({ ...o, member_id: memberId, cachedAt });
  } catch {
    // Best-effort — never block the live lookup that triggered this.
  }
}

export async function getCachedObligations(memberId: string): Promise<CachedObligation[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(OBLIGATIONS_STORE, "readonly");
    const index = tx.objectStore(OBLIGATIONS_STORE).index("member_id");
    const request = index.getAll(memberId);
    request.onsuccess = () => resolve(request.result as CachedObligation[]);
    request.onerror = () => reject(request.error);
  });
}
