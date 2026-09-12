"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { notificationsApi } from "@/lib/api/notifications";

const STATUS_STYLE: Record<string, string> = {
  sent: "bg-[var(--forest-soft)] text-[var(--forest)]",
  skipped_not_configured: "bg-[var(--surface)] text-[var(--ink-soft)]",
  skipped_no_address: "bg-[var(--surface)] text-[var(--ink-soft)]",
  failed: "bg-[var(--clay-red-soft)] text-[var(--clay-red)]",
};

const STATUS_LABEL: Record<string, string> = {
  sent: "Sent",
  skipped_not_configured: "Channel not configured",
  skipped_no_address: "No contact address",
  failed: "Failed",
};

const CHANNEL_LABEL: Record<string, string> = {
  console: "Console log",
  email: "Email",
  sms: "SMS",
  whatsapp: "WhatsApp",
};

const CATEGORY_LABEL: Record<string, string> = {
  defaulter_escalation: "Defaulter Escalation",
  family_expense_approval: "Family Expense Approval",
  old_debt: "Old Debt Alert",
  birthday: "Birthday",
  welfare_campaign_launched: "Welfare Campaign",
  subscription_reminder: "Subscription Reminder",
  notice_board_post: "Notice Board Post",
};

export default function NotificationsPage() {
  // 'Community members should have option where they can set or sort
  // the notifications.' All three filters are optional and combine —
  // "All categories" + "All" (read status) + "Newest first" is the
  // same, unfiltered list every member already saw before this existed.
  const [category, setCategory] = useState<string>("");
  const [readFilter, setReadFilter] = useState<"" | "true" | "false">("");
  const [ordering, setOrdering] = useState<"newest" | "oldest">("newest");

  const { data: notifications, isLoading } = useQuery({
    queryKey: ["notifications", category, readFilter, ordering],
    queryFn: () => notificationsApi.list({
      category: category || undefined,
      is_read: readFilter === "" ? undefined : readFilter === "true",
      ordering,
    }),
  });
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Your account</p>
        <h1 className="font-display mt-1 text-4xl">Notifications</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Every notice scoped to your role. Expand one to see exactly which channels were
          tried, and whether each one actually sent, was skipped, or failed — nothing here
          is silently swallowed.
        </p>
      </header>

      <main className="px-8 py-8">
        <div className="mb-4 flex flex-wrap gap-2">
          <select value={category} onChange={(e) => setCategory(e.target.value)} className="rounded-sm border border-[var(--rule)] bg-white px-2 py-1.5 text-sm">
            <option value="">All types</option>
            {Object.entries(CATEGORY_LABEL).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          <select value={readFilter} onChange={(e) => setReadFilter(e.target.value as typeof readFilter)} className="rounded-sm border border-[var(--rule)] bg-white px-2 py-1.5 text-sm">
            <option value="">Read and unread</option>
            <option value="false">Unread only</option>
            <option value="true">Read only</option>
          </select>
          <select value={ordering} onChange={(e) => setOrdering(e.target.value as typeof ordering)} className="rounded-sm border border-[var(--rule)] bg-white px-2 py-1.5 text-sm">
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
          </select>
        </div>

        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
        {notifications?.length === 0 && (
          <div className="border border-dashed border-[var(--rule)] px-6 py-10 text-center">
            <p className="font-display text-lg">Nothing to see right now</p>
          </div>
        )}
        <ol className="divide-y divide-[var(--rule)] border-y-2 border-[var(--ink)]">
          {notifications?.map((n, i) => (
            <li key={n.id}>
              <button
                onClick={() => setExpandedId(expandedId === n.id ? null : n.id)}
                className="flex w-full items-start justify-between gap-4 py-4 text-left"
              >
                <div className="flex gap-3">
                  <span className="font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(3, "0")}</span>
                  <div>
                    <p className="text-sm">{n.message}</p>
                    <p className="font-mono mt-1 text-xs text-[var(--ink-soft)]">
                      {new Date(n.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
                <span className="shrink-0 text-xs text-[var(--ink-soft)]">
                  {expandedId === n.id ? "Hide delivery ▲" : "Show delivery ▼"}
                </span>
              </button>
              {expandedId === n.id && <DeliveryAttempts notificationId={n.id} />}
            </li>
          ))}
        </ol>
      </main>
    </div>
  );
}

function DeliveryAttempts({ notificationId }: { notificationId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["delivery-attempts", notificationId],
    queryFn: () => notificationsApi.deliveryAttempts(notificationId),
  });

  return (
    <div className="mb-4 rounded-sm bg-[var(--surface)] p-3">
      {isLoading && <p className="text-xs text-[var(--ink-soft)]">Loading delivery attempts…</p>}
      {data?.length === 0 && <p className="text-xs text-[var(--ink-soft)]">No delivery attempts recorded.</p>}
      <ul className="space-y-1">
        {data?.map((a) => (
          <li key={a.id} className="flex items-center justify-between text-xs">
            <span>
              {CHANNEL_LABEL[a.channel]} {a.recipient_address && `→ ${a.recipient_address}`}
            </span>
            <span className={`rounded-full px-2 py-0.5 font-medium ${STATUS_STYLE[a.status]}`}>
              {STATUS_LABEL[a.status]}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
