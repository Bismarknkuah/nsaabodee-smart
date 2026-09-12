import { authFetch } from "./authFetch";
import { unwrapPaginated } from "./unwrapPaginated";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authFetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail?.toString() ?? `Request failed (${res.status})`);
  }
  const json = await res.json();
  return unwrapPaginated<T>(json) as T;
}

export interface CollectionPrediction {
  funeral_id: string;
  has_historical_data: boolean;
  expected_total: string;
  predicted_collection_rate: number | null;
  predicted_collected_total: string | null;
  based_on_funeral_count?: number;
  note?: string;
}

export interface InactiveMember {
  member_id: string;
  full_name: string;
  membership_number: string;
  last_registered: string;
}

export interface FuzzySearchResult {
  member_id: string;
  full_name: string;
  membership_number: string;
  match_score: number;
}

export interface MeetingSummaryResult {
  id: string;
  transcript: string;
  summary: string;
  decisions: string[];
  action_items: string[];
  created_at: string;
}

export interface SuspiciousTransactionFlag {
  id: string;
  payment: string;
  member_name: string;
  amount: string;
  reason: "amount_outlier" | "rapid_succession";
  detail: string;
  review_status: "unreviewed" | "confirmed" | "dismissed";
  flagged_at: string;
}

export const aiApi = {
  predictCollections: (funeralId: string) =>
    request<CollectionPrediction>(`/ai/funerals/${funeralId}/predict-collections/`),

  inactiveMembers: (inactiveDays = 180) =>
    request<InactiveMember[]>(`/ai/inactive-members/?inactive_days=${inactiveDays}`),

  search: (query: string) => request<FuzzySearchResult[]>(`/ai/search/?q=${encodeURIComponent(query)}`),

  summarizeMeeting: (transcript: string) =>
    request<MeetingSummaryResult>(`/ai/meeting-summary/`, { method: "POST", body: JSON.stringify({ transcript }) }),

  suspiciousTransactions: () => request<SuspiciousTransactionFlag[]>(`/suspicious-transactions/`),

  reviewSuspiciousTransaction: (id: string, reviewStatus: "confirmed" | "dismissed") =>
    request<SuspiciousTransactionFlag>(`/suspicious-transactions/${id}/`, {
      method: "PATCH",
      body: JSON.stringify({ review_status: reviewStatus }),
    }),
};
