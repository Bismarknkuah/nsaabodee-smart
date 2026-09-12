/**
 * 'Will be using thermal printer which supports both Bluetooth,
 * wireless, cables for the receipt printing.' This is the Bluetooth
 * path — Web Bluetooth lets the browser connect directly to a BLE
 * thermal printer and send it raw ESC/POS commands, no OS-level
 * driver or "system printer" registration needed at all. That makes
 * it genuinely more capable than the cable/wireless path (see
 * openReceiptPrintWindow.ts) for a printer that's actually Bluetooth,
 * since there's no print dialog or driver step in between.
 *
 * Real, honest limitations, stated directly rather than glossed over:
 * - Only Chrome and Edge implement Web Bluetooth (desktop and
 *   Android) — Safari and Firefox do not, on any platform, including
 *   iOS entirely (Apple has never shipped Web Bluetooth in WebKit).
 * - The GATT service/characteristic UUIDs used below match the most
 *   common generic 58mm/80mm Bluetooth thermal printer modules widely
 *   sold for POS use (the ones using the "SPP-over-BLE" pattern most
 *   generic Chinese thermal printer boards implement) — a different
 *   printer brand may use different UUIDs and simply won't be found;
 *   this is a best-effort default, not a universal guarantee.
 * - The connection has to be initiated by a real user click (Web
 *   Bluetooth requires a user gesture) — it can never be triggered
 *   automatically in the background.
 */

// The most common "printer service" UUID used by generic BLE thermal
// printer modules — not a universal standard, just the widest-spread
// convention among the inexpensive thermal printers commonly used for
// receipts.
const PRINTER_SERVICE_UUID = "000018f0-0000-1000-8000-00805f9b34fb";
const PRINTER_CHARACTERISTIC_UUID = "00002af1-0000-1000-8000-00805f9b34fb";

// BLE writes are chunked — most modules only reliably accept small
// packets per write (some negotiate a larger MTU, many don't), so
// sending the whole receipt in one write silently drops bytes on a
// lot of real hardware.
const CHUNK_SIZE = 20;

export function isBluetoothPrintingSupported(): boolean {
  return typeof navigator !== "undefined" && "bluetooth" in navigator;
}

function buildEscPosBytes(text: string): Uint8Array {
  const encoder = new TextEncoder();
  const ESC_INIT = new Uint8Array([0x1b, 0x40]); // ESC @ — initialize printer
  const body = encoder.encode(text.replace(/\r\n/g, "\n") + "\n\n\n");
  const CUT = new Uint8Array([0x1d, 0x56, 0x01]); // GS V 1 — partial cut, ignored harmlessly by printers that can't cut
  const combined = new Uint8Array(ESC_INIT.length + body.length + CUT.length);
  combined.set(ESC_INIT, 0);
  combined.set(body, ESC_INIT.length);
  combined.set(CUT, ESC_INIT.length + body.length);
  return combined;
}

let cachedDevice: BluetoothDevice | null = null;

/**
 * Prompts the user to pick a nearby Bluetooth printer (a real device
 * picker the browser itself shows — this can't be skipped or
 * automated, by design, for privacy). Remembers the picked device for
 * the rest of the session so a second receipt doesn't re-prompt.
 */
export async function connectToBluetoothPrinter(): Promise<BluetoothDevice> {
  if (!isBluetoothPrintingSupported()) {
    throw new Error("This browser doesn't support Bluetooth printing. Use Chrome or Edge, or print via a cable/system-registered printer instead.");
  }
  const device = await navigator.bluetooth!.requestDevice({
    filters: [{ services: [PRINTER_SERVICE_UUID] }],
    optionalServices: [PRINTER_SERVICE_UUID],
  });
  cachedDevice = device;
  return device;
}

export async function printReceiptViaBluetooth(text: string): Promise<void> {
  if (!isBluetoothPrintingSupported()) {
    throw new Error("This browser doesn't support Bluetooth printing. Use Chrome or Edge, or print via a cable/system-registered printer instead.");
  }

  const device = cachedDevice ?? (await connectToBluetoothPrinter());
  if (!device.gatt) {
    throw new Error("This device doesn't expose a Bluetooth GATT connection.");
  }

  const server = device.gatt.connected ? device.gatt : await device.gatt.connect();
  const service = await server.getPrimaryService(PRINTER_SERVICE_UUID);
  const characteristic = await service.getCharacteristic(PRINTER_CHARACTERISTIC_UUID);

  const bytes = buildEscPosBytes(text);
  for (let offset = 0; offset < bytes.length; offset += CHUNK_SIZE) {
    const chunk = bytes.slice(offset, offset + CHUNK_SIZE);
    await characteristic.writeValueWithoutResponse(chunk);
    // A short pause between chunks — writing too fast back-to-back is
    // a common, real cause of a printer silently dropping bytes.
    await new Promise((resolve) => setTimeout(resolve, 15));
  }
}

export function disconnectBluetoothPrinter(): void {
  if (cachedDevice?.gatt?.connected) {
    cachedDevice.gatt.disconnect();
  }
  cachedDevice = null;
}
