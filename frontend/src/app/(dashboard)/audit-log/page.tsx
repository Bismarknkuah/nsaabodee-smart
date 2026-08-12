"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { auditLogApi } from "@/lib/api/auditLog";
import { useAuthStore } from "@/store/authStore";
import { KpiTile } from "@/components/dashboard/DashboardVisuals";
import { IconWarning } from "@/components/icons/DashboardIcons";

const CATEGORY_LABEL: Record<string, string> = {
  community: "Community Lifecycle",
  role: "Role Assignment",
  funeral_opening: "Funeral Opening Decision",
  payment_reversal: "Payment Reversal Decision",
  billing: "Platform Billing",
  announcement: "Announcement / Homepage Feature",
};

const CATEGORY_ACCENT: Record<string, string> = {
  community: "var(--forest)",
  role: "var(--violet)",
  funeral_opening: "var(--clay-red)",
  payment_reversal: "var(--clay-red)",
  billing: "var(--gold)",
  announcement: "var(--violet)",
};

/**
 * "View audit logs" — one of the Platform Admin capabilities from the
 * spec that had nothing behind it until this batch. This is NOT a
 * replacement for the detailed, workflow-specific logs that already
 * exist (family structural changes, announcement review) — it's the
 * general layer covering everything else worth a permanent record:
 * community lifecycle, role grants, funeral-opening and
 * payment-reversal decisions, platform billing, and homepage-feature
 * grants.
 */
export default function AuditLogPage() {
  const currentUser = useAuthStore((s) => s.user);
  const isPlatformAdmin = currentUser?.role === "platform_admin" || currentUser?.is_superuser;
  const [category, setCategory] = useState("");

  const { data: entries, isLoading, error } = useQuery({
    queryKey: ["audit-log", category],
    queryFn: () => auditLogApi.list({ category: category || undefined }),
  });

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
          {isPlatformAdmin ? "Platform Administration" : "Community Administration"}
        </p>
        <h1 className="font-display mt-1 text-4xl">Audit Log</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          A permanent, append-only record of the decisions that matter most —
          {isPlatformAdmin
            ? " across every community on the platform."
            : " for your own community only."}
          {" "}This complements, not replaces, the detailed history already kept for
          families and announcements.
        </p>
      </header>

      <main className="px-8 py-8">
        <div className="flex flex-wrap items-center gap-4">
          <div className="grid grid-cols-2 gap-px border border-[var(--rule)] bg-[var(--rule)] sm:max-w-xs">
            <KpiTile label="Entries shown" value={entries?.length ?? 0} color="forest" icon={<IconWarning />} />
          </div>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="border border-[var(--rule)] px-3 py-2 text-sm"
          >
            <option value="">Every category</option>
            {Object.entries(CATEGORY_LABEL).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>

        <div className="mt-6">
          {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
          {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
          {entries?.length === 0 && (
            <div className="border border-dashed border-[var(--rule)] px-6 py-10 text-center">
              <p className="font-display text-lg">Nothing recorded yet</p>
            </div>
          )}
          <ol className="divide-y divide-[var(--rule)] border-y-2 border-[var(--ink)]">
            {entries?.map((e, i) => (
              <li key={e.id} className="flex items-start gap-3 py-4" style={{ borderLeft: `3px solid ${CATEGORY_ACCENT[e.category]}` }}>
                <span className="pl-3 font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(3, "0")}</span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-[10px] font-medium uppercase tracking-wide" style={{ color: CATEGORY_ACCENT[e.category] }}>
                      {CATEGORY_LABEL[e.category]}
                    </span>
                    {e.community_name && (
                      <span className="rounded-full bg-[var(--surface)] px-2 py-0.5 text-[10px] font-medium text-[var(--ink-soft)]">
                        {e.community_name}
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-sm">{e.description}</p>
                  <p className="mt-1 text-xs text-[var(--ink-soft)]">
                    {e.actor_username ? `${e.actor_username} (${e.actor_role.replace(/_/g, " ")})` : "System"} ·{" "}
                    {new Date(e.created_at).toLocaleString()}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </main>
    </div>
  );
}
