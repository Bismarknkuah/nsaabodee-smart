"use client";

import "@/styles/family-registry-tokens.css";
import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { supportApi } from "@/lib/api/support";

const STATUS_ACCENT: Record<string, string> = {
  open: "var(--gold)",
  in_progress: "var(--violet)",
  resolved: "var(--forest)",
  closed: "var(--ink-soft)",
};

/**
 * "Handle support tickets" — reachable by every user type, since a
 * Guest with no community is just as entitled to raise a problem as
 * anyone else. Only a Platform Admin sees the full queue, at
 * /support-queue.
 */
export default function SupportPage() {
  const { data: tickets, isLoading } = useQuery({ queryKey: ["my-tickets"], queryFn: supportApi.myTickets });
  const [activeTicketId, setActiveTicketId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const activeTicket = tickets?.find((t) => t.id === activeTicketId);

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Your account</p>
            <h1 className="font-display mt-1 text-4xl">Support</h1>
            <p className="mt-2 max-w-xl text-sm text-[var(--ink-soft)]">
              Raise a problem or a question — a platform administrator will reply here.
            </p>
          </div>
          <button onClick={() => setShowForm((s) => !s)} className="shrink-0 bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white">
            {showForm ? "Cancel" : "New ticket"}
          </button>
        </div>
      </header>

      <main className="px-8 py-8">
        {showForm && <NewTicketForm onDone={() => setShowForm(false)} />}

        <div className="mt-6 grid gap-6 lg:grid-cols-[20rem_1fr]">
          <div className="border border-[var(--rule)] bg-white">
            {isLoading && <p className="p-4 text-sm text-[var(--ink-soft)]">Loading…</p>}
            {tickets?.length === 0 && <p className="p-4 text-sm text-[var(--ink-soft)]">No tickets yet.</p>}
            {tickets?.map((t) => (
              <button
                key={t.id}
                onClick={() => setActiveTicketId(t.id)}
                className={`block w-full border-b border-[var(--rule)] px-4 py-3 text-left ${t.id === activeTicketId ? "bg-[var(--surface)]" : "hover:bg-[var(--surface)]"}`}
              >
                <span className="font-mono text-[10px] font-medium uppercase tracking-wide" style={{ color: STATUS_ACCENT[t.status] }}>
                  {t.status.replace(/_/g, " ")}
                </span>
                <p className="text-sm font-medium">{t.subject}</p>
              </button>
            ))}
          </div>

          <div>
            {activeTicket ? (
              <TicketThread key={activeTicket.id} ticket={activeTicket} />
            ) : (
              <p className="text-sm text-[var(--ink-soft)]">Select a ticket to view its conversation.</p>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

function NewTicketForm({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const submit = useMutation({
    mutationFn: () => supportApi.submit({ subject, description, priority }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["my-tickets"] }); onDone(); },
  });

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); submit.mutate(); }}
      className="border border-[var(--rule)] bg-white p-5"
    >
      <input
        value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject"
        className="w-full border-0 border-b-2 border-[var(--rule)] bg-transparent px-0 py-2 text-sm outline-none focus:border-[var(--forest)]"
      />
      <textarea
        value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Describe the problem or question…" rows={4}
        className="mt-3 w-full border border-[var(--rule)] p-2 text-sm outline-none focus:border-[var(--forest)]"
      />
      <div className="mt-3 flex items-center gap-3">
        <select value={priority} onChange={(e) => setPriority(e.target.value)} className="border border-[var(--rule)] px-2 py-1.5 text-sm">
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
          <option value="urgent">Urgent</option>
        </select>
        <button
          type="submit" disabled={submit.isPending || !subject.trim() || !description.trim()}
          className="bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {submit.isPending ? "Submitting…" : "Submit ticket"}
        </button>
      </div>
      {submit.isError && <p className="mt-2 text-sm text-[var(--clay-red)]">{(submit.error as Error).message}</p>}
    </form>
  );
}

function TicketThread({ ticket }: { ticket: { id: string; subject: string; description: string; status: string } }) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const { data: messages } = useQuery({ queryKey: ["ticket-messages", ticket.id], queryFn: () => supportApi.messages(ticket.id) });
  const post = useMutation({
    mutationFn: (content: string) => supportApi.postMessage(ticket.id, content),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["ticket-messages", ticket.id] }),
  });

  useEffect(() => { scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight }); }, [messages]);

  return (
    <div className="flex h-[32rem] flex-col border border-[var(--rule)] bg-white">
      <div className="border-b border-[var(--rule)] p-4">
        <h2 className="font-display text-lg">{ticket.subject}</h2>
        <p className="mt-1 text-sm text-[var(--ink-soft)]">{ticket.description}</p>
      </div>
      <div ref={scrollRef} className="flex-1 space-y-2 overflow-y-auto p-4">
        {messages?.map((m) => (
          <div key={m.id} className="border border-[var(--rule)] p-2 text-sm">
            <p className="font-mono text-[10px] uppercase tracking-wide text-[var(--ink-soft)]">{m.sender_username}</p>
            <p>{m.content}</p>
          </div>
        ))}
        {messages?.length === 0 && <p className="text-sm text-[var(--ink-soft)]">No replies yet.</p>}
      </div>
      <form
        onSubmit={(e) => { e.preventDefault(); if (draft.trim()) { post.mutate(draft.trim()); setDraft(""); } }}
        className="flex gap-2 border-t border-[var(--rule)] p-3"
      >
        <input
          value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Reply…"
          className="flex-1 border border-[var(--rule)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
        />
        <button type="submit" disabled={!draft.trim() || post.isPending} className="bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
          Send
        </button>
      </form>
    </div>
  );
}
