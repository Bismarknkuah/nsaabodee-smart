"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery } from "@tanstack/react-query";
import { membersApi } from "@/lib/api/members";
import { RegistryAnalyticsView } from "@/components/members/RegistryAnalyticsView";

/**
 * "His major role is to have access of the members data: total numbers
 * of the community members by gender, age, family by family, and more."
 * The scope is decided server-side from the role — a community-wide
 * registrar sees everyone, the Chief sees Town Elders, a family officer
 * sees only their own family.
 */
export default function MemberRegistryPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["member-registry-analytics"], queryFn: membersApi.registryAnalytics });
  const scopeLabel = data?.scope === "family" ? "Your family" : data?.scope === "town_elders" ? "Town Elders" : "Whole community";
  return (
    <div className="font-body min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="border-b border-[var(--border)] bg-[var(--card)] px-8 py-6">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-soft)]">{scopeLabel}</p>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight">Member Registry</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--text-soft)]">Who is registered, by status, gender, age, and family — and how registration has grown.</p>
      </header>
      <main className="space-y-6 px-8 py-8">
        {isLoading && <p className="text-sm text-[var(--text-soft)]">Loading…</p>}
        {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
        {data && <RegistryAnalyticsView data={data} />}
      </main>
    </div>
  );
}
