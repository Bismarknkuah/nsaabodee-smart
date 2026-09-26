import { authFetch } from "./authFetch";

export interface AuditLogEntry {
  id: string;
  category: "community" | "role" | "funeral_opening" | "payment_reversal" | "billing" | "announcement";
  action: string;
  actor_username: string;
  actor_role: string;
  community: string | null;
  community_name: string | null;
  target_type: string;
  target_id: string;
  target_label: string;
  description: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

async function request<T>(path: string): Promise<T> {
  const res = await authFetch(path);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail?.toString() ?? `Request failed (${res.status})`);
  }
  return res.json() as Promise<T>;
}

/**
 * "View audit logs" — Platform Admin sees the whole platform, a
 * Community Admin sees only their own community. Nobody else can
 * reach this at all, enforced on the backend, not just by hiding the
 * nav link here.
 */
export const auditLogApi = {
  list: (params?: { communityId?: string; category?: string }) => {
    const query = new URLSearchParams();
    if (params?.communityId) query.set("community_id", params.communityId);
    if (params?.category) query.set("category", params.category);
    const qs = query.toString();
    return request<AuditLogEntry[]>(`/audit-log/${qs ? `?${qs}` : ""}`);
  },
};
