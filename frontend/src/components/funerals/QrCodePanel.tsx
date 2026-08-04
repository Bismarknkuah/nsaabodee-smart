"use client";

import { useState } from "react";
import { funeralsApi } from "@/lib/api/funerals";

/**
 * "The community admin should be able to generate a barcode so that it
 * can be printed and pasted for guests to use to donate their gift or
 * contribute. Same as members or anyone once you scan it should take
 * you to what the barcode was meant for." A real, scannable QR code —
 * any ordinary phone camera opens it straight to the public Memorial
 * Page, which now also shows the community's payout account details.
 */
export function QrCodePanel({ funeralId }: { funeralId: string }) {
  const [data, setData] = useState<{ qr_code_base64: string; url: string } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await funeralsApi.getQrCode(funeralId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not generate the QR code.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="rounded-sm border border-[var(--rule)] bg-white p-6">
      <h2 className="font-display text-xl">Guest contribution QR code</h2>
      <p className="mt-1 text-sm text-[var(--ink-soft)]">
        Print this and post it where guests can see it — scanning it opens the public memorial
        page, which shows the community&apos;s payout account and a way to leave a tribute.
      </p>

      {!data ? (
        <button
          onClick={generate}
          disabled={loading}
          className="mt-4 rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {loading ? "Generating…" : "Generate QR code"}
        </button>
      ) : (
        <div className="mt-4">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={`data:image/png;base64,${data.qr_code_base64}`}
            alt="Scannable QR code linking to this funeral's public contribution page"
            className="h-48 w-48 border border-[var(--rule)] p-2"
          />
          <p className="mt-2 break-all font-mono text-xs text-[var(--ink-soft)]">{data.url}</p>
          <div className="mt-3 flex gap-3">
            <a
              href={`data:image/png;base64,${data.qr_code_base64}`}
              download={`funeral-qr-${funeralId}.png`}
              className="rounded-sm border border-[var(--rule)] px-3 py-1.5 text-xs font-medium"
            >
              Download
            </a>
            <button onClick={() => window.print()} className="rounded-sm border border-[var(--rule)] px-3 py-1.5 text-xs font-medium">
              Print
            </button>
          </div>
        </div>
      )}
      {error && <p className="mt-2 text-sm text-[var(--clay-red)]">{error}</p>}
    </section>
  );
}
