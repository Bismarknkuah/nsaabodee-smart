"use client";

import { useState } from "react";
import {
  useInLawRequests,
  useRequestInLawContribution,
  useDecideInLawRequest,
  useRecordInLawPayment,
} from "@/lib/hooks/useFunerals";
import { useFamilies } from "@/lib/hooks/useFamilies";
import { useFuneral } from "@/lib/hooks/useFunerals";
import { useAuthStore } from "@/store/authStore";
import { formatCedis } from "@/lib/formatCedis";
import type { PaymentMethod } from "@/types/funeral";

const STATUS_LABEL: Record<string, string> = {
  pending: "Pending approval",
  approved: "Approved — awaiting payment",
  rejected: "Rejected",
};

/**
 * 'The deceased family should be able to initiate an In-Law
 * Contribution Request... only after approval should the system
 * generate the actual financial obligation.' A request-and-approval
 * workflow, the opposite of every other ledger on this funeral's
 * page — nothing here is auto-generated, and every step (request,
 * decide, pay) is a deliberate, visible action.
 */
export function InLawContributionsPanel({ funeralId }: { funeralId: string }) {
  const user = useAuthStore((s) => s.user);
  const { data: funeral } = useFuneral(funeralId);
  const { data: requests, isLoading } = useInLawRequests(funeralId);
  const { data: families } = useFamilies(false);
  const requestMutation = useRequestInLawContribution(funeralId);
  const decideMutation = useDecideInLawRequest(funeralId);
  const payMutation = useRecordInLawPayment(funeralId);

  const [showRequestForm, setShowRequestForm] = useState(false);
  const [inLawFamilyId, setInLawFamilyId] = useState("");
  const [relationship, setRelationship] = useState("");
  const [requestedAmount, setRequestedAmount] = useState("");
  const [reason, setReason] = useState("");

  const [payingObligationId, setPayingObligationId] = useState<string | null>(null);
  const [payAmount, setPayAmount] = useState("");
  const [payMethod, setPayMethod] = useState<PaymentMethod>("cash");
  const [payCollectorName, setPayCollectorName] = useState(user?.username ?? "");

  const canRequest = Boolean(
    user && ["family_head", "family_secretary", "family_treasurer", "community_admin", "chairman", "secretary"].includes(user.role)
  );
  const canDecide = Boolean(user && ["community_admin", "chairman", "secretary"].includes(user.role));

  const otherFamilies = families?.filter((f) => f.status === "active" && f.id !== funeral?.deceased_family) ?? [];

  const submitRequest = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inLawFamilyId || !relationship.trim() || !requestedAmount) return;
    requestMutation.mutate(
      { in_law_family_id: inLawFamilyId, relationship: relationship.trim(), requested_amount: requestedAmount, reason: reason.trim() || undefined },
      {
        onSuccess: () => {
          setShowRequestForm(false);
          setInLawFamilyId("");
          setRelationship("");
          setRequestedAmount("");
          setReason("");
        },
      }
    );
  };

  const submitPayment = (e: React.FormEvent) => {
    e.preventDefault();
    if (!payingObligationId || !payAmount || !payCollectorName.trim()) return;
    payMutation.mutate(
      { obligationId: payingObligationId, input: { amount: payAmount, method: payMethod, collector_name: payCollectorName.trim() } },
      { onSuccess: () => setPayingObligationId(null) }
    );
  };

  return (
    <div className="rounded-sm bg-[var(--surface)] p-4">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-lg">In-Law Contribution</h3>
        {canRequest && !showRequestForm && (
          <button
            onClick={() => setShowRequestForm(true)}
            className="rounded-sm bg-[var(--forest)] px-3 py-1.5 text-sm font-medium text-white"
          >
            Request a contribution
          </button>
        )}
      </div>
      <p className="mt-1 text-sm text-[var(--ink-soft)]">
        A connected family — through marriage — contributing to this funeral. Nothing is owed until a
        request here is actually approved.
      </p>

      {showRequestForm && (
        <form onSubmit={submitRequest} className="mt-4 space-y-3 rounded-sm bg-white p-3">
          <div>
            <label className="text-sm font-medium">In-law family</label>
            <select
              value={inLawFamilyId}
              onChange={(e) => setInLawFamilyId(e.target.value)}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            >
              <option value="">Choose the connected family…</option>
              {otherFamilies.map((f) => (
                <option key={f.id} value={f.id}>{f.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-sm font-medium">Relationship</label>
            <input
              value={relationship}
              onChange={(e) => setRelationship(e.target.value)}
              placeholder="e.g. Kwame's wife's family"
              className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
          </div>
          <div>
            <label className="text-sm font-medium">Requested amount (GH₵)</label>
            <input
              type="number" min="0.01" step="0.01" value={requestedAmount}
              onChange={(e) => setRequestedAmount(e.target.value)}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
          </div>
          <div>
            <label className="text-sm font-medium">Reason / notes (optional)</label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={2}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
          </div>
          {requestMutation.error && <p className="text-sm text-[var(--clay-red)]">{requestMutation.error.message}</p>}
          <div className="flex justify-end gap-2">
            <button type="button" onClick={() => setShowRequestForm(false)} className="px-3 py-2 text-sm text-[var(--ink-soft)]">Cancel</button>
            <button
              type="submit"
              disabled={requestMutation.isPending}
              className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {requestMutation.isPending ? "Sending…" : "Send request"}
            </button>
          </div>
        </form>
      )}

      <div className="mt-4 space-y-2">
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
        {!isLoading && requests?.length === 0 && <p className="text-sm text-[var(--ink-soft)]">No In-Law contribution requests yet.</p>}
        {requests?.map((r) => (
          <div key={r.id} className="rounded-sm bg-white p-3 text-sm">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-medium">{r.in_law_family_name} — {formatCedis(r.requested_amount)}</p>
                <p className="text-xs text-[var(--ink-soft)]">{r.relationship}</p>
                {r.reason && <p className="mt-1 text-xs text-[var(--ink-soft)]">{r.reason}</p>}
              </div>
              <span className="whitespace-nowrap text-xs font-medium text-[var(--ink-soft)]">{STATUS_LABEL[r.status]}</span>
            </div>

            {r.status === "pending" && canDecide && (
              <div className="mt-2 flex gap-2">
                <button
                  onClick={() => decideMutation.mutate({ requestId: r.id, decision: "approve" })}
                  disabled={decideMutation.isPending}
                  className="rounded-sm bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
                >
                  Approve
                </button>
                <button
                  onClick={() => decideMutation.mutate({ requestId: r.id, decision: "reject" })}
                  disabled={decideMutation.isPending}
                  className="rounded-sm border border-[var(--rule)] px-3 py-1.5 text-xs font-medium disabled:opacity-60"
                >
                  Reject
                </button>
              </div>
            )}

            {r.obligation && r.obligation.payment_status !== "paid" && (
              <div className="mt-2">
                {payingObligationId === r.obligation.id ? (
                  <form onSubmit={submitPayment} className="mt-2 space-y-2 rounded-sm bg-[var(--surface)] p-2">
                    <div className="grid grid-cols-2 gap-2">
                      <input
                        type="number" min="0.01" step="0.01" value={payAmount}
                        onChange={(e) => setPayAmount(e.target.value)}
                        placeholder="Amount"
                        className="rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
                      />
                      <select
                        value={payMethod}
                        onChange={(e) => setPayMethod(e.target.value as PaymentMethod)}
                        className="rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
                      >
                        <option value="cash">Cash</option>
                        <option value="mobile_money">Mobile Money</option>
                        <option value="bank">Bank</option>
                        <option value="other">Other</option>
                      </select>
                    </div>
                    <input
                      value={payCollectorName}
                      onChange={(e) => setPayCollectorName(e.target.value)}
                      placeholder="Collector's name"
                      className="w-full rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
                    />
                    {payMutation.error && <p className="text-xs text-[var(--clay-red)]">{payMutation.error.message}</p>}
                    <div className="flex justify-end gap-2">
                      <button type="button" onClick={() => setPayingObligationId(null)} className="px-2 py-1 text-xs text-[var(--ink-soft)]">Cancel</button>
                      <button
                        type="submit"
                        disabled={payMutation.isPending}
                        className="rounded-sm bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
                      >
                        {payMutation.isPending ? "Recording…" : "Record payment"}
                      </button>
                    </div>
                  </form>
                ) : (
                  <button
                    onClick={() => { setPayingObligationId(r.obligation!.id); setPayAmount(r.obligation!.balance); }}
                    className="mt-1 rounded-sm border border-[var(--rule)] px-3 py-1.5 text-xs font-medium"
                  >
                    Record payment — {formatCedis(r.obligation.balance)} outstanding
                  </button>
                )}
              </div>
            )}
            {r.obligation?.payment_status === "paid" && (
              <p className="mt-2 text-xs font-medium text-[var(--forest)]">Fully paid.</p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
