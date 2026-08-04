import type {
  ApprovalProgress,
  ContributionObligation,
  DeskAssignment,
  DeskType,
  FuneralCommitteePosition,
  FuneralEvent,
  FuneralSummary,
  PaymentMethod,
  PaymentStatus,
  RateType,
} from "@/types/funeral";
import { authFetch } from "./authFetch";
import { unwrapPaginated } from "./unwrapPaginated";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await authFetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const message = body.detail?.toString() ?? Object.values(body).flat().join(" ") ?? `Request failed (${res.status})`;
    throw new Error(message);
  }
  const json = await res.json();
  return unwrapPaginated<T>(json) as T;
}

export const funeralsApi = {
  getQrCode: (funeralId: string) =>
    request<{ qr_code_base64: string; url: string }>(`/funerals/${funeralId}/qr-code/`),

  /** "Every funeral creates a committee workspace... Custom positions allowed." */
  listCommitteePositions: (funeralId: string) =>
    request<FuneralCommitteePosition[]>(`/funerals/${funeralId}/committee-positions/`),
  appointCommitteePosition: (funeralId: string, memberId: string, title: string) =>
    request<FuneralCommitteePosition>(`/funerals/${funeralId}/committee-positions/`, {
      method: "POST",
      body: JSON.stringify({ member_id: memberId, title }),
    }),
  removeCommitteePosition: (funeralId: string, positionId: string) =>
    request<void>(`/funerals/${funeralId}/committee-positions/${positionId}/`, { method: "DELETE" }),
  myCommitteePositions: () => request<FuneralCommitteePosition[]>(`/funerals/my-committee-positions/`),

  list: (status: "active" | "closed" | "cancelled" | "pending_approval" | "all" = "active") =>
    request<FuneralEvent[]>(`/funerals/${status === "all" ? "" : `?status=${status}`}`),

  get: (id: string) => request<FuneralEvent>(`/funerals/${id}/`),

  create: (input: {
    deceased_name: string;
    deceased_gender: "male" | "female";
    deceased_family_id: string;
    date_of_death: string;
    collection_start_date: string;
    burial_date?: string;
    funeral_date?: string;
    collection_end_date?: string;
    own_family_amount?: string;
    general_male_amount?: string;
    general_female_amount?: string;
  }) => request<FuneralEvent>(`/funerals/`, { method: "POST", body: JSON.stringify(input) }),

  /** "Is the family head who will open the ledger." Same shape as create(), minus deceased_family_id — a Family Head is scoped to their own family automatically. Community Admin+ can still pass it to request on behalf of any family. */
  requestOpening: (input: {
    deceased_name: string;
    deceased_gender: "male" | "female";
    deceased_family_id?: string;
    date_of_death: string;
    collection_start_date: string;
    burial_date?: string;
    funeral_date?: string;
  }) => request<FuneralEvent>(`/funerals/request/`, { method: "POST", body: JSON.stringify(input) }),

  approveOpening: (id: string) => request<FuneralEvent & { approval_progress: ApprovalProgress }>(`/funerals/${id}/approve-opening/`, { method: "POST" }),
  rejectOpening: (id: string) => request<FuneralEvent>(`/funerals/${id}/reject-opening/`, { method: "POST" }),
  approvalProgress: (id: string) => request<ApprovalProgress>(`/funerals/${id}/approval-progress/`),

  /** "The family head and secretary of the deceased family can set an amount for each member." Only while still pending approval. */
  listMemberRateOverrides: (funeralId: string) =>
    request<{ member: string; member_name: string; amount: string }[]>(`/funerals/${funeralId}/member-rate-overrides/`),
  setMemberRateOverrides: (funeralId: string, overrides: Record<string, string>) =>
    request<{ member: string; member_name: string; amount: string }[]>(`/funerals/${funeralId}/member-rate-overrides/`, {
      method: "POST",
      body: JSON.stringify({ overrides }),
    }),

  /** "Head of the family should be able to add one or more users... some who could be a member or not, to be on the funeral desk." */
  listDeskAssignments: (funeralId: string) => request<DeskAssignment[]>(`/funerals/${funeralId}/desk-assignments/`),

  /** "A dignified public page for the funeral" — the authenticated, family/admin-only management side. */
  manageMemorialPage: (funeralId: string, input: { tribute_message?: string; photo?: File; show_contribution_total?: boolean; is_published?: boolean }) => {
    const form = new FormData();
    if (input.tribute_message !== undefined) form.set("tribute_message", input.tribute_message);
    if (input.photo) form.set("photo", input.photo);
    if (input.show_contribution_total !== undefined) form.set("show_contribution_total", String(input.show_contribution_total));
    if (input.is_published !== undefined) form.set("is_published", String(input.is_published));
    return authFetch(`/funerals/${funeralId}/memorial/manage/`, { method: "POST", body: form }).then(async (res) => {
      if (!res.ok) throw new Error("Could not save the memorial page.");
      return res.json();
    });
  },
  listTributesForManagement: (funeralId: string) =>
    request<{ id: string; author_name: string; message: string; is_approved: boolean; created_at: string }[]>(`/funerals/${funeralId}/memorial/tributes/manage/`),
  approveTribute: (funeralId: string, tributeId: string) =>
    request(`/funerals/${funeralId}/memorial/tributes/${tributeId}/approve/`, { method: "POST" }),
  removeTribute: (funeralId: string, tributeId: string) =>
    request(`/funerals/${funeralId}/memorial/tributes/${tributeId}/`, { method: "DELETE" }),

  /** "Add AI features to make it greater" — drafts a starting-point tribute; never saves it automatically. */
  draftTribute: (funeralId: string, keyDetails: string) =>
    request<{ draft: string }>(`/ai/funerals/${funeralId}/draft-tribute/`, {
      method: "POST",
      body: JSON.stringify({ key_details: keyDetails }),
    }),

  assignDeskWorker: (
    funeralId: string,
    input: { desk_type: DeskType; user_id?: string; new_username?: string; new_password?: string; new_email?: string }
  ) => request<DeskAssignment>(`/funerals/${funeralId}/desk-assignments/`, { method: "POST", body: JSON.stringify(input) }),
  removeDeskAssignment: (funeralId: string, assignmentId: string) =>
    request<void>(`/funerals/${funeralId}/desk-assignments/${assignmentId}/`, { method: "DELETE" }),

  close: (id: string) => request<FuneralEvent>(`/funerals/${id}/close/`, { method: "POST" }),

  summary: (id: string) => request<FuneralSummary>(`/funerals/${id}/summary/`),

  obligations: (id: string, filters?: { rate_type?: RateType; payment_status?: PaymentStatus }) => {
    const params = new URLSearchParams();
    if (filters?.rate_type) params.set("rate_type", filters.rate_type);
    if (filters?.payment_status) params.set("payment_status", filters.payment_status);
    const qs = params.toString();
    return request<ContributionObligation[]>(`/funerals/${id}/obligations/${qs ? `?${qs}` : ""}`);
  },

  recordPayment: (
    funeralId: string,
    obligationId: string,
    input: { amount: string; method: PaymentMethod; client_op_id?: string }
  ) =>
    request<{ id: string; receipt_number: string }>(`/funerals/${funeralId}/obligations/${obligationId}/record-payment/`, {
      method: "POST",
      body: JSON.stringify(input),
    }),
};
