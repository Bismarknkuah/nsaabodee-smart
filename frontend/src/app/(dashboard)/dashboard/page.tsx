"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/store/authStore";
import { dashboardRouteForRole } from "@/lib/dashboardRoutes";

/**
 * The one thin thing this route does now: figure out which real,
 * separate dashboard page this role owns, and go there. No shared
 * data-fetching, no shared rendering — that all lives in each role's
 * own page now, so editing one can never touch another.
 */
export default function DashboardRouterPage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    // "When using Personal Dashboard" — an executive who has switched
    // context lands on exactly what a Community Member sees, regardless
    // of their actual stored role, which this never touches.
    const destination = user?.active_context === "personal" ? "/dashboard/member" : dashboardRouteForRole(user?.role);
    router.replace(destination);
  }, [user?.role, user?.active_context, router]);

  return (
    <div className="font-body flex min-h-screen items-center justify-center bg-[var(--paper)] text-sm text-[var(--ink-soft)]">
      Loading your dashboard…
    </div>
  );
}
