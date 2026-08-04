"use client";

import "@/styles/family-registry-tokens.css";
import { useEffect, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { messagingApi } from "@/lib/api/messaging";
import { useAuthStore } from "@/store/authStore";

const CHANNEL_LABEL: Record<string, string> = {
  platform: "Platform",
  community: "Community",
  family: "Family",
};

/**
 * "Add message channel to all user types and should be a channel from
 * top to down." Every role lands here with at least one channel —
 * their community's, plus their family's if they're in one, plus the
 * platform channel if they're a Community Admin or Platform Admin.
 */
export default function MessagingPage() {
  const currentUser = useAuthStore((s) => s.user);
  const { data: channels, isLoading } = useQuery({ queryKey: ["my-channels"], queryFn: messagingApi.myChannels });
  const [activeChannelId, setActiveChannelId] = useState<string | null>(null);

  useEffect(() => {
    if (!activeChannelId && channels && channels.length > 0) setActiveChannelId(channels[0].id);
  }, [channels, activeChannelId]);

  const activeChannel = channels?.find((c) => c.id === activeChannelId);

  return (
    <div className="font-body flex min-h-screen flex-col bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Channels</p>
        <h1 className="font-display mt-1 text-4xl">Messaging</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Your community, your family (if you have one), and — if you&apos;re a Community or
          Platform Admin — the platform channel connecting every community&apos;s leadership.
        </p>
      </header>

      <div className="flex flex-1">
        <aside className="w-64 shrink-0 border-r border-[var(--rule)] bg-white">
          {isLoading && <p className="p-4 text-sm text-[var(--ink-soft)]">Loading…</p>}
          {channels?.map((c) => (
            <button
              key={c.id}
              onClick={() => setActiveChannelId(c.id)}
              className={`block w-full border-b border-[var(--rule)] px-4 py-3 text-left ${
                c.id === activeChannelId ? "bg-[var(--surface)]" : "hover:bg-[var(--surface)]"
              }`}
            >
              <p className="font-mono text-[10px] font-medium uppercase tracking-wide text-[var(--ink-soft)]">{CHANNEL_LABEL[c.channel_type]}</p>
              <p className="text-sm font-medium">{c.name}</p>
            </button>
          ))}
        </aside>

        <section className="flex flex-1 flex-col">
          {activeChannel ? (
            <ChannelPane key={activeChannel.id} channel={activeChannel} currentUsername={currentUser?.username} />
          ) : (
            !isLoading && <p className="p-6 text-sm text-[var(--ink-soft)]">No channel selected.</p>
          )}
        </section>
      </div>
    </div>
  );
}

function ChannelPane({ channel, currentUsername }: { channel: { id: string; name: string }; currentUsername?: string }) {
  const qc = useQueryClient();
  const [draft, setDraft] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data: messages, isLoading } = useQuery({ queryKey: ["channel-messages", channel.id], queryFn: () => messagingApi.messages(channel.id) });
  const post = useMutation({
    mutationFn: (content: string) => messagingApi.post(channel.id, content),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["channel-messages", channel.id] }),
  });

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!draft.trim() || post.isPending) return;
    post.mutate(draft.trim());
    setDraft("");
  };

  return (
    <>
      <div className="border-b border-[var(--rule)] px-6 py-4">
        <h2 className="font-display text-xl">{channel.name}</h2>
      </div>
      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto p-6">
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
        {messages?.length === 0 && <p className="text-sm text-[var(--ink-soft)]">No messages yet — be the first to say something.</p>}
        {messages?.map((m) => (
          <div key={m.id} className={`flex ${m.sender_username === currentUsername ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[70%] px-3 py-2 text-sm ${
                m.sender_username === currentUsername ? "bg-[var(--forest)] text-white" : "border border-[var(--rule)] bg-white"
              }`}
            >
              {m.sender_username !== currentUsername && (
                <p className="mb-0.5 font-mono text-[10px] uppercase tracking-wide text-[var(--ink-soft)]">
                  {m.sender_username} · {m.sender_role.replace(/_/g, " ")}
                </p>
              )}
              <p>{m.content}</p>
            </div>
          </div>
        ))}
        {post.isError && <p className="text-sm text-[var(--clay-red)]">{(post.error as Error).message}</p>}
      </div>
      <form onSubmit={submit} className="flex gap-2 border-t border-[var(--rule)] p-4">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Type a message…"
          className="flex-1 border border-[var(--rule)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
        />
        <button
          type="submit"
          disabled={!draft.trim() || post.isPending}
          className="bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          Send
        </button>
      </form>
    </>
  );
}
