"use client";

import { useState } from "react";
import { useRecordGift, useDonationAccounts } from "@/lib/hooks/useGifts";
import { useFuneral } from "@/lib/hooks/useFunerals";
import { reportsApi } from "@/lib/api/reports";
import { openReceiptPrintWindow } from "@/lib/openReceiptPrintWindow";
import { enqueueOperation, newClientOpId } from "@/lib/offlineQueue";
import { useOnlineStatus } from "@/lib/hooks/useOnlineStatus";
import { useAuthStore } from "@/store/authStore";
import type { DonorCategory, GiftPaymentMethod } from "@/types/gift";
import { Field, FormSection, FIELD_INPUT_CLASS } from "@/components/forms/FormPrimitives";

const CATEGORY_LABEL: Record<DonorCategory, string> = {
  guest: "Guest",
  town_leader: "Town Leader (King / Elder)",
  other: "Other",
};

export function RecordGiftDialog({ funeralId, onClose }: { funeralId: string; onClose: () => void }) {
  const { data: funeral } = useFuneral(funeralId);
  const { mutate, isPending, error } = useRecordGift(funeralId);
  const { data: donationAccounts } = useDonationAccounts(funeralId);
  const online = useOnlineStatus();
  const currentUser = useAuthStore((s) => s.user);

  // Ordered to match how this is actually used at the table: who's
  // giving, who it's for, how they're connected, then contact details —
  // "the cashier will only take the name of the one donating, and the
  // name of the person he's donating [to], and the relationship... and
  // the contact... and where [they stay]."
  const [donorName, setDonorName] = useState("");
  const [receivedByMemberId, setReceivedByMemberId] = useState("");
  const [relationshipToRecipient, setRelationshipToRecipient] = useState("");
  const [donorPhone, setDonorPhone] = useState("");
  const [donorHometown, setDonorHometown] = useState("");
  const [donorCategory, setDonorCategory] = useState<DonorCategory>("guest");
  const [connectedRelativeName, setConnectedRelativeName] = useState("");
  // 'Town A sends 15 people to the funeral. One representative may
  // present a contribution on behalf of Town A... without necessarily
  // creating 15 separate financial obligations.' Left blank means an
  // ordinary, individual gift — the existing, unaffected default.
  const [delegationSize, setDelegationSize] = useState("");
  const [amountCash, setAmountCash] = useState("");
  const [giftItem, setGiftItem] = useState("");
  const [estimatedValue, setEstimatedValue] = useState("");
  const [method, setMethod] = useState<GiftPaymentMethod>("cash");
  // 'Any collector have to input in their names for them to know who
  // they paid to.'
  const [collectorName, setCollectorName] = useState(currentUser?.username ?? "");
  const [recordedDonationId, setRecordedDonationId] = useState<string | null>(null);
  const [queuedOffline, setQueuedOffline] = useState(false);
  const [queueError, setQueueError] = useState<string | null>(null);

  const receiverName = donationAccounts?.find((a) => a.member === receivedByMemberId)?.member_name;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!donorName.trim()) return;
    if (!amountCash && !giftItem) return;
    if (!collectorName.trim()) return;

    const payload = {
      donor_name: donorName.trim(),
      donor_phone: donorPhone || undefined,
      donor_category: donorCategory,
      donor_hometown: donorHometown || undefined,
      connected_relative_name: connectedRelativeName || undefined,
      relationship_to_recipient: relationshipToRecipient || undefined,
      received_by_member_id: receivedByMemberId || undefined,
      amount_cash: amountCash || "0",
      gift_item: giftItem || undefined,
      estimated_item_value: giftItem ? estimatedValue || undefined : undefined,
      payment_method: amountCash ? method : "not_applicable" as GiftPaymentMethod,
      collector_name: collectorName.trim(),
      delegation_size: delegationSize ? Number(delegationSize) : undefined,
    };

    if (!online) {
      // Same idempotent queue the Front Desk's cash payments use — a
      // gift recorded with no signal syncs automatically later through
      // the identical record-gift call an online submission would have
      // made, "for transparency and accountability" applying exactly
      // the same whether it happened live or was synced afterward.
      const clientOpId = newClientOpId();
      try {
        await enqueueOperation({
          id: clientOpId, type: "gift", funeralId,
          payload: { ...payload, client_op_id: clientOpId },
          label: `${donorName.trim()} — ${amountCash ? `GH₵${amountCash}` : giftItem}`,
          createdAt: new Date().toISOString(),
        });
        setQueuedOffline(true);
      } catch (err) {
        setQueueError(err instanceof Error ? err.message : "Could not save this offline — try again.");
      }
      return;
    }

    mutate(payload, { onSuccess: (donation) => setRecordedDonationId(donation.id) });
  };

  const printReceipt = async () => {
    if (!recordedDonationId) return;
    const text = await reportsApi.giftReceiptText(recordedDonationId);
    openReceiptPrintWindow(text);
  };

  if (queuedOffline) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
        <div className="font-body w-full max-w-sm rounded-sm bg-[var(--surface)] p-6 text-center text-[var(--ink)] shadow-xl">
          <h2 className="font-display text-xl">Saved on this device</h2>
          <p className="mt-2 text-sm text-[var(--ink-soft)]">
            No connection right now — this gift will sync automatically the moment you&apos;re
            back online. No receipt to print or view until then.
          </p>
          <button onClick={onClose} className="mt-4 rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white">
            Done
          </button>
        </div>
      </div>
    );
  }

  if (recordedDonationId) {
    const isCash = Boolean(amountCash) && method === "cash";
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
        <div className="font-body w-full max-w-sm rounded-sm bg-[var(--surface)] p-6 text-center text-[var(--ink)] shadow-xl">
          <h2 className="font-display text-xl">Thank you, {donorName}!</h2>
          <p className="mt-2 text-sm">
            Your gift to {receiverName ?? `${funeral?.deceased_family_name ?? "the"} family`} in loving memory
            of {funeral?.deceased_name} has been recorded.
          </p>
          <p className="mt-2 text-sm text-[var(--ink-soft)]">
            {isCash
              ? "Print a receipt for the donor now, since this was given in person."
              : "No printing needed — this receipt is electronic, and if the donor is a registered member it's already in their own dashboard."}
          </p>
          {receiverName && (
            <p className="mt-2 text-xs text-[var(--ink-soft)]">
              This will show up on {receiverName}&apos;s own dashboard — for transparency and accountability.
            </p>
          )}
          <div className="mt-4 flex justify-center gap-2">
            <button onClick={onClose} className="rounded-sm border border-[var(--rule)] px-4 py-2 text-sm">Done</button>
            <button onClick={printReceipt} className="rounded-sm px-4 py-2 text-sm font-medium text-white" style={{ backgroundColor: "var(--violet)" }}>
              {isCash ? "Print receipt" : "View receipt"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="font-body flex max-h-[85vh] w-full max-w-md flex-col overflow-hidden rounded-sm bg-[var(--surface)] text-[var(--ink)] shadow-xl">
        <div className="shrink-0 border-b border-[var(--rule)] p-6 pb-4">
          <div className="flex items-start justify-between gap-4">
            <h2 className="font-display text-xl">Record a gift donation</h2>
            <button onClick={onClose} className="shrink-0 text-[var(--ink-soft)] hover:text-[var(--ink)]" aria-label="Close">
              ✕
            </button>
          </div>
          {funeral && (
            <p className="mt-1 text-sm font-medium text-[var(--violet)]">
              For {funeral.deceased_name}&apos;s funeral — died {new Date(funeral.date_of_death).toLocaleDateString()}
            </p>
          )}
        </div>
        <div className="overflow-y-auto p-6 pt-4">
        <p className="mt-1 text-sm text-[var(--ink-soft)]">
          This is Ledger 2 — separate from mandatory contributions. The donor doesn&apos;t
          need to be a registered member, and can give any amount they choose.
        </p>
        {!online && (
          <p className="mt-2 rounded-sm bg-[var(--surface)] px-3 py-2 text-xs text-[var(--gold)]">
            No connection right now — this will save on this device and sync automatically later.
          </p>
        )}

        <form onSubmit={submit} className="mt-4 space-y-5">
          <FormSection label="Donor">
            <Field label="Donor's name" wide>
              <input
                value={donorName}
                autoFocus
                onChange={(e) => setDonorName(e.target.value)}
                className={FIELD_INPUT_CLASS}
              />
            </Field>

            {donationAccounts && donationAccounts.length > 0 && (
              <Field
                label="Give this to"
                wide
                hint="Choosing a name here means this gift shows up on that person's own dashboard — for transparency and accountability."
              >
                <select
                  value={receivedByMemberId}
                  onChange={(e) => setReceivedByMemberId(e.target.value)}
                  className={FIELD_INPUT_CLASS}
                >
                  <option value="">General gift (no specific receiver)</option>
                  {donationAccounts.map((a) => (
                    <option key={a.id} value={a.member}>{a.member_name}</option>
                  ))}
                </select>
              </Field>
            )}

            {receivedByMemberId && (
              <Field label={`Donor's relationship to ${receiverName}`} wide>
                <input
                  value={relationshipToRecipient}
                  onChange={(e) => setRelationshipToRecipient(e.target.value)}
                  placeholder="e.g. Friend, Cousin, Workmate"
                  className={FIELD_INPUT_CLASS}
                />
              </Field>
            )}

            <Field label="Donor's phone">
              <input
                value={donorPhone}
                onChange={(e) => setDonorPhone(e.target.value)}
                className={FIELD_INPUT_CLASS}
              />
            </Field>
            <Field label="Where they stay">
              <input
                value={donorHometown}
                onChange={(e) => setDonorHometown(e.target.value)}
                placeholder="e.g. Kumasi"
                className={FIELD_INPUT_CLASS}
              />
            </Field>
          </FormSection>

          <details className="rounded-sm bg-white p-3 text-sm">
            <summary className="cursor-pointer font-medium text-[var(--ink-soft)]">More details (optional)</summary>
            <div className="mt-3 grid grid-cols-2 gap-3">
              <Field label="Who is this?">
                <select
                  value={donorCategory}
                  onChange={(e) => setDonorCategory(e.target.value as DonorCategory)}
                  className={FIELD_INPUT_CLASS}
                >
                  {Object.entries(CATEGORY_LABEL).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </Field>
              <Field label="Here because of">
                <input
                  value={connectedRelativeName}
                  onChange={(e) => setConnectedRelativeName(e.target.value)}
                  placeholder="Which relative of the deceased?"
                  className={FIELD_INPUT_CLASS}
                />
              </Field>
              <Field
                label="Giving on behalf of a group?"
                wide
                hint="Leave blank for an ordinary individual gift. Fill in when one representative — e.g. a town or family delegation — is giving on behalf of a group."
              >
                <input
                  type="number" min="1" step="1" value={delegationSize}
                  onChange={(e) => setDelegationSize(e.target.value)}
                  placeholder="Number of people this gift represents"
                  className={FIELD_INPUT_CLASS}
                />
              </Field>
            </div>
          </details>

          <FormSection label="Cash (optional)">
            <Field label="Amount">
              <input
                type="number" min="0" step="0.01" value={amountCash}
                onChange={(e) => setAmountCash(e.target.value)}
                className={FIELD_INPUT_CLASS}
              />
            </Field>
            <Field label="Method">
              <select
                value={method}
                onChange={(e) => setMethod(e.target.value as GiftPaymentMethod)}
                className={FIELD_INPUT_CLASS}
              >
                <option value="cash">Cash</option>
                <option value="mobile_money">Mobile Money</option>
                <option value="bank">Bank</option>
                <option value="other">Other</option>
              </select>
            </Field>
          </FormSection>

          <FormSection label="Gift item (optional)">
            <Field label="Item">
              <input
                value={giftItem}
                onChange={(e) => setGiftItem(e.target.value)}
                placeholder="e.g. a bag of rice"
                className={FIELD_INPUT_CLASS}
              />
            </Field>
            <Field label="Estimated value">
              <input
                type="number" min="0" step="0.01" value={estimatedValue}
                onChange={(e) => setEstimatedValue(e.target.value)}
                disabled={!giftItem}
                className={`${FIELD_INPUT_CLASS} disabled:opacity-50`}
              />
            </Field>
          </FormSection>

          <Field label="Your name">
            <input
              value={collectorName}
              onChange={(e) => setCollectorName(e.target.value)}
              placeholder="Who is physically collecting this?"
              className={FIELD_INPUT_CLASS}
            />
          </Field>

          {error && <p className="text-sm text-[var(--clay-red)]">{error.message}</p>}
          {queueError && <p className="text-sm text-[var(--clay-red)]">{queueError}</p>}

          <div className="flex justify-end gap-2 border-t border-[var(--rule)] pt-4">
            <button type="button" onClick={onClose} className="px-3 py-2 text-sm text-[var(--ink-soft)]">
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending || !collectorName.trim()}
              className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {isPending ? "Recording…" : online ? "Record & issue receipt" : "Save on this device"}
            </button>
          </div>
        </form>
        </div>
      </div>
    </div>
  );
}
