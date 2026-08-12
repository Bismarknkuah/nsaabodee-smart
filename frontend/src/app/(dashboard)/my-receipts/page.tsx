"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useMyReceipts } from "@/lib/hooks/useReports";
import { useMyDonationsReceived } from "@/lib/hooks/useGifts";
import { formatCedis } from "@/lib/formatCedis";
import { PrintReceiptButton } from "@/components/PrintReceiptButton";
import { reportsApi } from "@/lib/api/reports";
import { giftsApi } from "@/lib/api/gifts";
import type { ReceiptEntry } from "@/types/reports";

export default function MyReceiptsPage() {
  const { data, isLoading } = useMyReceipts();
  const { data: donationsReceived } = useMyDonationsReceived();
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  const downloadDonationsPdf = async () => {
    setDownloadingPdf(true);
    try {
      await giftsApi.openMyDonationsReceivedPdf();
    } finally {
      setDownloadingPdf(false);
    }
  };

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
          Your account
        </p>
        <h1 className="font-display mt-1 text-4xl">My Receipts</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Every receipt for a payment you made, or a gift you gave, lives here — whether you
          paid in person and got a printed slip, or paid by Mobile Money and only ever had an
          electronic one. This page is the same either way.
        </p>
      </header>

      {donationsReceived && donationsReceived.donation_count > 0 && (
        <div className="border-b border-[var(--rule)] px-8 py-6" style={{ backgroundColor: "var(--violet-soft)" }}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="font-mono text-xs uppercase tracking-widest" style={{ color: "var(--violet)" }}>
                For transparency and accountability
              </p>
              <h2 className="font-display mt-1 text-xl" style={{ color: "var(--violet)" }}>
                Donations received in my name
              </h2>
              <p className="mt-1 text-sm text-[var(--ink-soft)]">
                Every gift anyone has ever given specifically to you, as a registered donation
                receiver — cash or Mobile Money alike.
              </p>
            </div>
            <button
              onClick={downloadDonationsPdf}
              disabled={downloadingPdf}
              className="shrink-0 rounded-sm border px-3 py-1.5 text-xs font-medium disabled:opacity-60"
              style={{ borderColor: "var(--violet)", color: "var(--violet)" }}
            >
              {downloadingPdf ? "Preparing…" : "Download PDF"}
            </button>
          </div>
          <div className="mt-3 flex items-center gap-6">
            <div>
              <p className="text-xs text-[var(--ink-soft)]">Total received</p>
              <p className="font-mono text-2xl font-semibold">{formatCedis(donationsReceived.total_received)}</p>
            </div>
            <div>
              <p className="text-xs text-[var(--ink-soft)]">Donations</p>
              <p className="font-mono text-2xl font-semibold">{donationsReceived.donation_count}</p>
            </div>
          </div>

          <div className="mt-4 overflow-hidden rounded-sm border border-[var(--rule)] bg-white">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[var(--rule)] text-left text-xs uppercase tracking-wide text-[var(--ink-soft)]">
                  <th className="px-3 py-2">Donor</th>
                  <th className="px-3 py-2">Phone</th>
                  <th className="px-3 py-2">Hometown</th>
                  <th className="px-3 py-2">For</th>
                  <th className="px-3 py-2">When</th>
                  <th className="px-3 py-2 text-right">Amount</th>
                </tr>
              </thead>
              <tbody>
                {donationsReceived.entries.map((e) => (
                  <tr key={e.receipt_number} className="border-b border-[var(--rule)] last:border-b-0">
                    <td className="px-3 py-2 font-medium">{e.donor_name}</td>
                    <td className="px-3 py-2 text-[var(--ink-soft)]">{e.donor_phone || "—"}</td>
                    <td className="px-3 py-2 text-[var(--ink-soft)]">{e.donor_hometown || "—"}</td>
                    <td className="px-3 py-2 text-[var(--ink-soft)]">{e.deceased_name}</td>
                    <td className="px-3 py-2 text-xs text-[var(--ink-soft)]">{e.paid_on} {e.paid_at_time}</td>
                    <td className="px-3 py-2 text-right font-mono">{formatCedis(e.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <main className="px-8 py-8">
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}

        {data && !data.has_member_profile && (
          <div className="rounded-sm border border-dashed border-[var(--rule)] px-6 py-10 text-center">
            <p className="font-display text-lg">No member profile linked yet</p>
            <p className="mt-1 text-sm text-[var(--ink-soft)]">
              Ask a Community Administrator to link your login to your member profile to see
              your receipts here.
            </p>
          </div>
        )}

        {data?.has_member_profile && data.receipts.length === 0 && (
          <div className="rounded-sm border border-dashed border-[var(--rule)] px-6 py-10 text-center">
            <p className="font-display text-lg">No receipts yet</p>
          </div>
        )}

        <ul className="divide-y divide-[var(--rule)] border-y border-[var(--rule)]">
          {data?.receipts.map((r) => <ReceiptRow key={r.receipt_number} receipt={r} />)}
        </ul>
      </main>
    </div>
  );
}

function ReceiptRow({ receipt }: { receipt: ReceiptEntry }) {
  const amount = receipt.ledger === "contribution" ? receipt.amount : receipt.total_value;
  const who = receipt.ledger === "contribution" ? receipt.member_name : receipt.donor_name;
  const family = receipt.ledger === "contribution" ? receipt.family_name : receipt.recipient_family_name;

  const getText = () =>
    receipt.ledger === "contribution"
      ? reportsApi.contributionReceiptText(receipt.payment_id!)
      : reportsApi.giftReceiptText(receipt.donation_id!);

  return (
    <li className="flex items-center gap-4 py-4">
      <span
        aria-hidden
        className="h-8 w-1.5 shrink-0 rounded-full"
        style={{ backgroundColor: receipt.ledger === "contribution" ? "var(--forest)" : "var(--violet)" }}
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p className="font-medium">{receipt.funeral_deceased_name}</p>
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              receipt.ledger === "contribution"
                ? "bg-[var(--forest-soft)] text-[var(--forest)]"
                : "bg-[var(--violet-soft)] text-[var(--violet)]"
            }`}
          >
            {receipt.ledger === "contribution" ? "Contribution" : "Gift given"}
          </span>
          <DeliveryBadge channel={receipt.delivery_channel} />
        </div>
        <p className="font-mono mt-0.5 text-xs text-[var(--ink-soft)]">
          {receipt.receipt_number} · {who} {family ? `· ${family}` : ""} · {receipt.date} {receipt.time}
        </p>
      </div>
      <span className="font-mono font-medium">{formatCedis(amount ?? "0")}</span>
      <PrintReceiptButton
        getText={getText}
        label="View receipt"
        className="rounded-sm border border-[var(--rule)] px-3 py-1.5 text-xs font-medium hover:border-[var(--forest)] hover:text-[var(--forest)]"
      />
      <button
        onClick={() =>
          receipt.ledger === "contribution"
            ? reportsApi.openContributionReceiptPdf(receipt.payment_id!)
            : reportsApi.openGiftReceiptPdf(receipt.donation_id!)
        }
        className="rounded-sm border border-[var(--rule)] px-3 py-1.5 text-xs font-medium hover:border-[var(--forest)] hover:text-[var(--forest)]"
      >
        Download PDF
      </button>
    </li>
  );
}

function DeliveryBadge({ channel }: { channel: "physical" | "electronic" }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
        channel === "physical" ? "bg-[var(--gold-soft)] text-[var(--gold)]" : "bg-[var(--surface)] text-[var(--ink-soft)]"
      }`}
    >
      {channel === "physical" ? "Printed in person" : "Electronic"}
    </span>
  );
}
