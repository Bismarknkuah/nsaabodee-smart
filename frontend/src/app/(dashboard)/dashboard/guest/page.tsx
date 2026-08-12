"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api/dashboard";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";

interface PublicOverview {
  active_funerals: { id: string; deceased_name: string; deceased_family_name: string }[];
}

/** The most limited access in the platform, so the plainest page — a welcome and a single, honest list. Nothing to manage, nothing to decide. */
export default function GuestDashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const overview = data?.sections.public_overview as PublicOverview | undefined;

  return (
    <DashboardPageShell folio="Folio IX" register="Visitor's Notice" title="Welcome" subtitle="Here's what's currently happening in this community.">
      {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
      {overview && (
        <div className="lg:col-span-2 mx-auto w-full max-w-xl">
          {overview.active_funerals.length === 0 ? (
            <p className="text-center text-sm text-[var(--ink-soft)]">There's no funeral currently active in this community.</p>
          ) : (
            <ul className="divide-y divide-[var(--rule)] border-y border-[var(--rule)]">
              {overview.active_funerals.map((f) => (
                <li key={f.id} className="py-3 text-center text-sm">
                  <span className="font-display text-lg">{f.deceased_name}</span>
                  <span className="block text-[var(--ink-soft)]">{f.deceased_family_name}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </DashboardPageShell>
  );
}
