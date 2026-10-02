import { useEffect, useState } from "react";

/**
 * A real, live connectivity signal — not a guess. `navigator.onLine`
 * plus the browser's own `online`/`offline` events, the same mechanism
 * every offline-aware web app uses. It can occasionally be optimistic
 * (reports "online" on a captive portal with no real internet), which
 * is why the actual queue-draining logic in useOfflineSync still treats
 * a failed sync attempt as "try again later" rather than a hard error.
 */
export function useOnlineStatus(): boolean {
  const [online, setOnline] = useState(true);

  useEffect(() => {
    setOnline(navigator.onLine);
    const goOnline = () => setOnline(true);
    const goOffline = () => setOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  return online;
}
