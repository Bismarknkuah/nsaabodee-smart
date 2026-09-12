"use client";

import { useEffect, useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * Every page in this app calls useQuery/useMutation from
 * @tanstack/react-query, which throws at runtime without a
 * QueryClientProvider somewhere above it in the tree — there wasn't one
 * anywhere in this codebase until this file. `useState` (rather than a
 * module-level constant) is the standard Next.js App Router pattern
 * specifically so each request gets its own QueryClient on the server,
 * while the client still reuses one instance across re-renders.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            staleTime: 30_000,
          },
        },
      })
  );

  useEffect(() => {
    // public/sw.js — runtime-caches pages/assets actually visited while
    // online, so a reload with no connection doesn't just fail outright.
    // Registration failing (unsupported browser, insecure context on
    // plain HTTP in some setups) is silently ignored — the app already
    // works fully online-only without it, this is a pure enhancement.
    //
    // Production only, deliberately: the static-asset cache-first
    // strategy in sw.js assumes _next/static/ filenames are immutable
    // (true in a real production build, where content changes produce
    // a new hashed filename). In `next dev`, filenames aren't hashed
    // the same way, so the same URL can serve different code across
    // dev-server rebuilds — a service worker registered during
    // development would then keep serving an old, cached bundle
    // indefinitely, invisible in Incognito (which never persists one)
    // but persisting in a regular browser profile across restarts.
    if (process.env.NODE_ENV === "production" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
