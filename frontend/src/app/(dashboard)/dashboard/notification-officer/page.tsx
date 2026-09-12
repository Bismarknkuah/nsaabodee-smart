"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery } from "@tanstack/react-query";
import { dashboardApi } from "@/lib/api/dashboard";
import { DashboardPageShell } from "@/components/dashboard/DashboardPageShell";
import { KpiTile, SectionCard, FolioLink } from "@/components/dashboard/DashboardVisuals";

interface NotificationsOverview {
  recent_notifications: { id: string; message: string }[];
  delivery_totals_by_status: Record<string, number>;
}

/** A dispatch board — status tiles arranged as a control panel, weighted toward whatever needs attention (failed/pending), since that's the actual job of this role. */
export default function NotificationOfficerDashboardPage() {
  const { data, isLoading, error } = useQuery({ queryKey: ["dashboard"], queryFn: dashboardApi.get });
  const overview = data?.sections.notifications_overview as NotificationsOverview | undefined;
  const colorFor = (status: string): "forest" | "clay" | "gold" =>
    status === "sent" || status === "delivered" ? "forest" : status === "failed" ? "clay" : "gold";

  const entries = overview ? Object.entries(overview.delivery_totals_by_status) : [];
  const failedOrPending = entries.filter(([s]) => s !== "sent" && s !== "delivered");
  const succeeded = entries.filter(([s]) => s === "sent" || s === "delivered");

  return (
    <DashboardPageShell folio="Folio VII" register="Dispatch Log" title="Notification Status" subtitle="Delivery status across every channel this community uses.">
      {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
      {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
      {overview && (
        <>
          {failedOrPending.length > 0 && (
            <div className="lg:col-span-2 grid grid-cols-2 gap-px border-2 border-[var(--clay-red)] bg-[var(--rule)] sm:grid-cols-4">
              {failedOrPending.map(([status, count]) => (
                <KpiTile key={status} label={`${status.replace(/_/g, " ")} — needs attention`} value={count} color={colorFor(status)} />
              ))}
            </div>
          )}
          <SectionCard title="Delivered" eyebrow="Successfully sent" accent="forest">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              {succeeded.map(([status, count]) => (
                <KpiTile key={status} label={status.replace(/_/g, " ")} value={count} color="forest" />
              ))}
              {succeeded.length === 0 && <p className="text-sm text-[var(--ink-soft)]">Nothing delivered yet.</p>}
            </div>
            <div className="mt-4"><FolioLink href="/notifications">View all notifications</FolioLink></div>
          </SectionCard>
        </>
      )}
    </DashboardPageShell>
  );
}
