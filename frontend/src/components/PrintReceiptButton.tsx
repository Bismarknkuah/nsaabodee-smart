"use client";

import { useState } from "react";
import { openReceiptPrintWindow } from "@/lib/openReceiptPrintWindow";
import { isBluetoothPrintingSupported, printReceiptViaBluetooth } from "@/lib/bluetoothPrinter";

/**
 * 'Will be using thermal printer which supports both Bluetooth,
 * wireless, cables for the receipt printing.' One button, offering
 * whichever of these two real, working paths actually applies:
 * cable/wireless printers registered as a system printer (via the
 * standard print dialog), or a Bluetooth printer the browser can
 * connect to directly. The Bluetooth option only appears at all in a
 * browser that actually supports it (Chrome/Edge) — never shown as a
 * false promise in Safari or Firefox.
 */
export function PrintReceiptButton({
  getText, getQrCode, label = "Print receipt", className = "",
}: {
  getText: () => string | Promise<string>;
  /** Optional — "the receipt should have a bar scan code so that they can scan to confirm their payment." Omit for a receipt type that has no QR code of its own yet. */
  getQrCode?: () => Promise<{ qr_code_base64: string; verify_url: string } | null>;
  label?: string;
  className?: string;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [bluetoothStatus, setBluetoothStatus] = useState<"idle" | "connecting" | "error">("idle");
  const [bluetoothError, setBluetoothError] = useState<string | null>(null);
  const bluetoothAvailable = isBluetoothPrintingSupported();

  const printViaSystem = async () => {
    const text = await getText();
    const qrCode = getQrCode ? await getQrCode().catch(() => null) : null;
    openReceiptPrintWindow(text, qrCode?.qr_code_base64);
    setMenuOpen(false);
  };

  const printViaBluetooth = async () => {
    setBluetoothStatus("connecting");
    setBluetoothError(null);
    try {
      const text = await getText();
      const qrCode = getQrCode ? await getQrCode().catch(() => null) : null;
      await printReceiptViaBluetooth(text, qrCode?.verify_url);
      setBluetoothStatus("idle");
      setMenuOpen(false);
    } catch (err) {
      setBluetoothStatus("error");
      setBluetoothError(err instanceof Error ? err.message : "Couldn't reach the printer.");
    }
  };

  if (!bluetoothAvailable) {
    // Only one real option here — skip the menu entirely rather than show a dropdown with one item.
    return (
      <button onClick={printViaSystem} className={className}>
        {label}
      </button>
    );
  }

  return (
    <div className="relative inline-block">
      <button onClick={() => setMenuOpen((o) => !o)} className={className}>
        {label}
      </button>
      {menuOpen && (
        <div className="absolute right-0 z-20 mt-1 w-56 rounded-lg border border-[var(--rule)] bg-white p-1 text-sm shadow-lg">
          <button onClick={printViaSystem} className="block w-full rounded-lg px-3 py-2 text-left hover:bg-[var(--bg)]">
            Print (cable / system printer)
          </button>
          <button
            onClick={printViaBluetooth}
            disabled={bluetoothStatus === "connecting"}
            className="block w-full rounded-lg px-3 py-2 text-left hover:bg-[var(--bg)] disabled:opacity-60"
          >
            {bluetoothStatus === "connecting" ? "Connecting…" : "Print via Bluetooth"}
          </button>
          {bluetoothError && <p className="px-3 py-1 text-xs text-[var(--clay-red)]">{bluetoothError}</p>}
        </div>
      )}
    </div>
  );
}
