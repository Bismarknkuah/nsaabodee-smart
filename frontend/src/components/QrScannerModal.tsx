"use client";

import { useEffect, useRef, useState } from "react";

/**
 * "Printing of receipt should have a bar code scanner." Every member
 * already has a real, scannable QR code on their digital membership
 * card (see members/models.py's Member.qr_payload) that opens straight
 * to that member's profile — this is the other half: a Collector at
 * the desk scanning that same code to jump straight to a payment
 * screen, instead of typing a name to search.
 *
 * Uses the browser's native BarcodeDetector API rather than adding an
 * external scanning library — the same honest, Chrome/Edge-only
 * limitation already accepted for Bluetooth printing (see
 * bluetoothPrinter.ts). Safari and Firefox don't implement it; the
 * name-search box this sits alongside on the Front Desk page still
 * works everywhere as the fallback it always was.
 */
export function isQrScanningSupported(): boolean {
  return typeof window !== "undefined" && "BarcodeDetector" in window;
}

interface QrScannerModalProps {
  onDetected: (rawValue: string) => void;
  onClose: () => void;
}

export function QrScannerModal({ onDetected, onClose }: QrScannerModalProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let animationFrame: number;

    async function start() {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }

        // @ts-expect-error — BarcodeDetector isn't yet in TypeScript's lib.dom types.
        const detector = new window.BarcodeDetector({ formats: ["qr_code"] });

        const scanFrame = async () => {
          if (cancelled || !videoRef.current) return;
          try {
            const codes = await detector.detect(videoRef.current);
            if (codes.length > 0) {
              onDetected(codes[0].rawValue);
              return; // Stop scanning once we've found one — the caller decides what happens next.
            }
          } catch {
            // A single failed detection pass (e.g. the video frame wasn't ready yet) isn't fatal — just try again next frame.
          }
          animationFrame = requestAnimationFrame(scanFrame);
        };
        scanFrame();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Could not access the camera.");
      }
    }

    start();
    return () => {
      cancelled = true;
      cancelAnimationFrame(animationFrame);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
  }, [onDetected]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70">
      <div className="w-full max-w-sm rounded-lg bg-white p-4">
        <div className="flex items-center justify-between">
          <p className="font-display text-lg">Scan membership card</p>
          <button onClick={onClose} className="text-sm text-[var(--ink-soft)]">Close</button>
        </div>
        {error ? (
          <p className="mt-3 text-sm text-[var(--clay-red)]">{error}</p>
        ) : (
          <>
            <video ref={videoRef} muted playsInline className="mt-3 w-full rounded-lg bg-black" />
            <p className="mt-2 text-xs text-[var(--ink-soft)]">Hold the member&apos;s card or receipt QR code up to the camera.</p>
          </>
        )}
      </div>
    </div>
  );
}

/**
 * Every member's qr_payload is a real URL, "{FRONTEND_BASE_URL}/members/{id}"
 * (see members/models.py). Extracts just the id from that shape;
 * returns null for anything scanned that isn't one of this platform's
 * own member QR codes, so an unrelated QR code doesn't silently do
 * something unexpected.
 */
export function extractMemberIdFromScan(rawValue: string): string | null {
  const match = rawValue.match(/\/members\/([0-9a-f-]{36})\/?$/i);
  return match ? match[1] : null;
}
