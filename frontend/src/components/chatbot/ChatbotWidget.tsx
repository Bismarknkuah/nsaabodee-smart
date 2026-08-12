"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { chatbotApi } from "@/lib/api/chatbot";

/**
 * "Add chatbot to all user types." Mounted once, in the shared
 * Sidebar layout, so it appears on every page under (dashboard)/ for
 * every role — no per-page wiring needed. A help assistant only: it
 * explains how the platform works and where to go, and is explicitly
 * instructed never to invent a specific financial figure.
 */
export function ChatbotWidget() {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const qc = useQueryClient();
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: history } = useQuery({ queryKey: ["chatbot-history"], queryFn: chatbotApi.history, enabled: open });
  const ask = useMutation({
    mutationFn: (message: string) => chatbotApi.ask(message),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["chatbot-history"] }),
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [history, ask.isPending]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!draft.trim() || ask.isPending) return;
    ask.mutate(draft.trim());
    setDraft("");
  };

  return (
    <>
      {open && (
        <div className="fixed bottom-20 right-5 z-40 flex h-[28rem] w-[22rem] flex-col border border-[var(--rule,#ded6c4)] bg-white shadow-2xl">
          <div className="flex items-center justify-between border-b-2 border-[var(--ink,#20291f)] px-4 py-3">
            <div>
              <p className="font-mono text-[10px] font-medium uppercase tracking-[0.16em] text-[var(--ink-soft,#5c6459)]">Help</p>
              <p className="font-display text-lg text-[var(--ink,#20291f)]">Ask Nsaabodeɛ Smart</p>
            </div>
            <button onClick={() => setOpen(false)} className="text-[var(--ink-soft,#5c6459)] hover:text-[var(--ink,#20291f)]" aria-label="Close chat">
              ✕
            </button>
          </div>

          <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto bg-[var(--paper,#fbfaf7)] p-4">
            {(!history || history.length === 0) && !ask.isPending && (
              <p className="text-sm text-[var(--ink-soft,#5c6459)]">
                Ask how to use any part of the platform — recording a payment, requesting a
                funeral opening, assigning a task, anything. This won&apos;t know your own
                balances or records; it&apos;ll point you to the right page for those.
              </p>
            )}
            {history?.map((m) => (
              <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] px-3 py-2 text-sm ${
                    m.role === "user" ? "bg-[var(--forest,#2b6e4e)] text-white" : "border border-[var(--rule,#ded6c4)] bg-white text-[var(--ink,#20291f)]"
                  }`}
                >
                  {m.content}
                </div>
              </div>
            ))}
            {ask.isPending && (
              <div className="flex justify-start">
                <div className="border border-[var(--rule,#ded6c4)] bg-white px-3 py-2 text-sm text-[var(--ink-soft,#5c6459)]">Thinking…</div>
              </div>
            )}
            {ask.isError && <p className="text-sm text-[var(--clay-red,#a93b2e)]">{(ask.error as Error).message}</p>}
          </div>

          <form onSubmit={submit} className="flex gap-2 border-t border-[var(--rule,#ded6c4)] p-3">
            <input
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Type a question…"
              className="flex-1 border border-[var(--rule,#ded6c4)] px-3 py-2 text-sm outline-none focus:border-[var(--forest,#2b6e4e)]"
            />
            <button
              type="submit"
              disabled={!draft.trim() || ask.isPending}
              className="bg-[var(--forest,#2b6e4e)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              Send
            </button>
          </form>
        </div>
      )}

      <button
        onClick={() => setOpen((v) => !v)}
        className="fixed bottom-5 right-5 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-[var(--forest,#2b6e4e)] text-white shadow-lg hover:brightness-110"
        aria-label={open ? "Close help chat" : "Open help chat"}
      >
        {open ? (
          <span className="text-xl">✕</span>
        ) : (
          <svg viewBox="0 0 24 24" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.8">
            <path d="M4 5.5h16v11H8.5L4 20V5.5z" strokeLinejoin="round" />
            <path d="M8 10h8M8 13.5h5" strokeLinecap="round" />
          </svg>
        )}
      </button>
    </>
  );
}
