"use client";

import "@/styles/family-registry-tokens.css";
import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { supportApi } from "@/lib/api/support";
import { useAuthStore } from "@/store/authStore";
import { KpiTile } from "@/components/dashboard/DashboardVisuals";
import { IconWarning } from "@/components/icons/DashboardIcons";

const STATUS_ACCENT: Record<string, string> = {
  open: "var(--gold)",
  in_progress: "var(--violet)",
  resolved: "var(--forest)",
  closed: "var(--ink-soft)",
};

export default function SupportQueuePage() {
  const user = useAuthStore((s) => s.user);
  const isPlatformAdmin = user?.role === "platform_admin";
  const [statusFilter, setStatusFilter] = useState("");
  const { data: tickets, isLoading } = useQuery({ queryKey: ["all-tickets", statusFilter], queryFn: () => supportApi.allTickets(statusFilter || undefined) });
  const [activeTicketId, setActiveTicketId] = useState<string | null>(null);
  const activeTicket = tickets?.find((t) => t.id === activeTicketId);
  const openCount = tickets?.filter((t) => t.status === "open").length ?? 0;

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
          {isPlatformAdmin ? "Platform Administration" : "Community Administration"}
        </p>
        <h1 className="font-display mt-1 text-4xl">Support Queue</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          {isPlatformAdmin
            ? "Escalations from every community and temporary administrator, platform-wide — every other member or executive's ticket is already being handled by their own community administrator."
            : "Every ticket from your own community's members and executives — your own escalations go to the Platform Administrator instead."}
        </p>
      </header>

      <main className="px-8 py-8">
        <div className="flex flex-wrap items-center gap-4">
          <div className="grid grid-cols-2 gap-px border border-[var(--rule)] bg-[var(--rule)] sm:max-w-xs">
            <KpiTile label="Open" value={openCount} color={openCount > 0 ? "gold" : "forest"} icon={<IconWarning />} />
            <KpiTile label="Total shown" value={tickets?.length ?? 0} color="forest" />
          </div>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="border border-[var(--rule)] px-3 py-2 text-sm">
            <option value="">Every status</option>
            <option value="open">Open</option>
            <option value="in_progress">In Progress</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed</option>
          </select>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-[22rem_1fr]">
          <div className="border border-[var(--rule)] bg-white">
            {isLoading && <p className="p-4 text-sm text-[var(--ink-soft)]">Loading…</p>}
            {tickets?.length === 0 && <p className="p-4 text-sm text-[var(--ink-soft)]">Nothing here.</p>}
            {tickets?.map((t) => (
              <button
                key={t.id}
                onClick={() => setActiveTicketId(t.id)}
                className={`block w-full border-b border-[var(--rule)] px-4 py-3 text-left ${t.id === activeTicketId ? "bg-[var(--surface)]" : "hover:bg-[var(--surface)]"}`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] font-medium uppercase tracking-wide" style={{ color: STATUS_ACCENT[t.status] }}>
                    {t.status.replace(/_/g, " ")}
                  </span>
                  <span className="text-[10px] text-[var(--ink-soft)]">{t.priority}</span>
                </div>
                <p className="text-sm font-medium">{t.subject}</p>
                <p className="text-xs text-[var(--ink-soft)]">{t.submitted_by_username}{t.community_name ? ` · ${t.community_name}` : ""}</p>
              </button>
            ))}
          </div>

          <div>
            {activeTicket ? <QueueTicketPanel key={activeTicket.id} ticket={activeTicket} /> : <p className="text-sm text-[var(--ink-soft)]">Select a ticket.</p>}
          </div>
        </div>
      </main>
    </div>
  );
}

function QueueTicketPanel({ ticket }: { ticket: { id: string; subject: string; description: string; status: string; submitted_by_username: string } }) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const { data: messages } = useQuery({ queryKey: ["ticket-messages", ticket.id], queryFn: () => supportApi.messages(ticket.id) });
  const post = useMutation({
    mutationFn: (content: string) => supportApi.postMessage(ticket.id, content),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ticket-messages", ticket.id] }),
  });
  const updateStatus = useMutation({
    mutationFn: (status: string) => supportApi.updateStatus(ticket.id, status),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["all-tickets"] }); },
  });

  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight }); }, [messages]);

  return (
    <div className="flex h-[32rem] flex-col border border-[var(--rule)] bg-white">
      <div className="flex items-start justify-between gap-4 border-b border-[var(--rule)] p-4">
        <div>
          <h2 className="font-display text-lg">{ticket.subject}</h2>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">{ticket.description}</p>
          <p className="mt-1 text-xs text-[var(--ink-soft)]">From {ticket.submitted_by_username}</p>
        </div>
        <select
          value={ticket.status}
          onChange={(e) => updateStatus.mutate(e.target.value)}
          className="shrink-0 border border-[var(--rule)] px-2 py-1.5 text-xs"
        >
          <option value="open">Open</option>
          <option value="in_progress">In Progress</option>
          <option value="resolved">Resolved</option>
          <option value="closed">Closed</option>
        </select>
      </div>
      <div ref={scrollRef} className="flex-1 space-y-2 overflow-y-auto p-4">
        {messages?.map((m) => (
          <div key={m.id} className="border border-[var(--rule)] p-2 text-sm">
            <p className="font-mono text-[10px] uppercase tracking-wide text-[var(--ink-soft)]">{m.sender_username}</p>
            <p>{m.content}</p>
          </div>
        ))}
      </div>
      <form
        onSubmit={(e) => { e.preventDefault(); if (draft.trim()) { post.mutate(draft.trim()); setDraft(""); } }}
        className="flex gap-2 border-t border-[var(--rule)] p-3"
      >
        <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Reply…" className="flex-1 border border-[var(--rule)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]" />
        <button type="submit" disabled={!draft.trim() || post.isPending} className="bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60">Send</button>
      </form>
    </div>
  );
}
