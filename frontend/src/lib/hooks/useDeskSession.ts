import { useEffect, useState } from "react";

export type ReceiptDeliveryMethod = "print" | "sms";
export type PrintMethod = "system" | "bluetooth";

export interface DeskSession {
  collectorName: string;
  deliveryMethod: ReceiptDeliveryMethod;
  // Only meaningful when deliveryMethod is "print" — which physical
  // connection the thermal printer uses. Chosen once at desk-opening
  // time rather than re-offered after every single payment, since
  // "once paid, printing should be so easier" is the whole point of
  // asking for it upfront instead of per receipt.
  printMethod: PrintMethod;
}

const STORAGE_KEY = "front-desk-session";

function readStoredSession(): DeskSession | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (
      typeof parsed.collectorName === "string" &&
      (parsed.deliveryMethod === "print" || parsed.deliveryMethod === "sms") &&
      (parsed.printMethod === "system" || parsed.printMethod === "bluetooth")
    ) {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

/**
 * "So before any collector clicks open desk, the person has to fill
 * some forms to select either to print receipt or send SMS, type
 * his name, so that he doesn't have to type his name for all the
 * payment." Set once per shift (sessionStorage, so it survives a
 * page refresh but clears when the tab actually closes), then reused
 * automatically for every payment recorded during that session.
 */
export function useDeskSession() {
  const [session, setSessionState] = useState<DeskSession | null>(null);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setSessionState(readStoredSession());
    setHydrated(true);
  }, []);

  const setSession = (next: DeskSession) => {
    setSessionState(next);
    if (typeof window !== "undefined") {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    }
  };

  const clearSession = () => {
    setSessionState(null);
    if (typeof window !== "undefined") {
      window.sessionStorage.removeItem(STORAGE_KEY);
    }
  };

  return { session, setSession, clearSession, hydrated };
}
