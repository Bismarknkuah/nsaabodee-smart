"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { Sidebar } from "@/components/layout/Sidebar";

/**
 * Wraps every page under app/(dashboard)/ — families, funerals, members,
 * reports, my-receipts, notifications, contribution-rules, all of it.
 * Login itself lives outside this route group (app/login/) specifically
 * so it's the one page that never runs this guard.
 *
 * This only owns the (dashboard) route group's layout, not the app's
 * true root layout — if this source tree is dropped into an existing
 * Next.js app (per this project's README), that root layout is the
 * host app's own file and isn't something this project ships.
 */
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { accessToken, hydrate } = useAuthStore();
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    hydrate();
    setHydrated(true);
  }, [hydrate]);

  useEffect(() => {
    if (hydrated && !accessToken) {
      router.replace("/login");
    }
  }, [hydrated, accessToken, router]);

  if (!hydrated || !accessToken) {
    return null;
  }

  return <Sidebar>{children}</Sidebar>;
}
