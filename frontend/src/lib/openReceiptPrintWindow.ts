/**
 * 'Will be using thermal printer which supports both Bluetooth,
 * wireless, cables for the receipt printing, so the receipt should be
 * modernized.' This function handles the cable/wireless case — any
 * thermal printer registered as a real system printer (via USB, or a
 * network/Wi-Fi printer with its own driver installed), which is the
 * only way a browser can reach a wireless printer at all; browser
 * security genuinely prevents a raw network socket connection to a
 * printer directly from JavaScript. For a Bluetooth thermal printer,
 * see bluetoothPrinter.ts instead — Web Bluetooth lets the browser
 * connect directly, no OS-level driver needed.
 *
 * @page below sizes the output for an actual thermal roll (80mm is
 * the most common width) instead of full A4/Letter paper with huge
 * margins around a few lines of text — this alone is most of what
 * "modernized" means for the cable/system-printer path, since the
 * printer itself (once selected in the print dialog) handles the
 * physical printing exactly as it always has.
 */
function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

export function openReceiptPrintWindow(text: string, widthMm: 58 | 80 = 80) {
  const win = window.open("", "_blank", "width=380,height=600");
  if (!win) return;
  win.document.write(`
    <html>
      <head>
        <title>Receipt</title>
        <style>
          @page { size: ${widthMm}mm auto; margin: 2mm; }
          * { box-sizing: border-box; }
          body {
            font-family: "IBM Plex Mono", ui-monospace, monospace;
            font-size: 12px;
            line-height: 1.4;
            white-space: pre-wrap;
            padding: 12px;
            width: ${widthMm}mm;
            margin: 0 auto;
          }
          .toolbar { display: flex; gap: 8px; margin-top: 16px; }
          button {
            flex: 1;
            padding: 10px 16px;
            font-size: 13px;
            font-weight: 600;
            border: 1px solid #ccc;
            border-radius: 4px;
            background: #fff;
            cursor: pointer;
          }
          button.primary { background: #2B6E4E; color: #fff; border-color: #2B6E4E; }
          @media print {
            .toolbar { display: none; }
            body { padding: 0; }
          }
        </style>
      </head>
      <body>
        <pre>${escapeHtml(text)}</pre>
        <div class="toolbar">
          <button class="primary" onclick="window.print()">Print</button>
          <button onclick="window.close()">Close</button>
        </div>
      </body>
    </html>
  `);
  win.document.close();
  // A real thermal-receipt workflow expects the print dialog to open
  // immediately, not wait for a manual click — the button above stays
  // as a way to print again (e.g. a second copy) without closing and
  // reopening this window.
  win.focus();
  setTimeout(() => win.print(), 200);
}
