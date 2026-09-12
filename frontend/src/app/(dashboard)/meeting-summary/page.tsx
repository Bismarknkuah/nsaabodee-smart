"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useSummarizeMeeting } from "@/lib/hooks/useAiFeatures";

export default function MeetingSummaryPage() {
  const [transcript, setTranscript] = useState("");
  const { mutate, data, isPending, error } = useSummarizeMeeting();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!transcript.trim()) return;
    mutate(transcript.trim());
  };

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
          Community Administration
        </p>
        <h1 className="font-display mt-1 text-4xl">Meeting Summary</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Paste a meeting transcript below to get a draft summary, decisions, and action items.
          This calls a real language model — if your administrator hasn&apos;t configured an API
          key yet, you&apos;ll see a clear message below rather than a fake result. Treat the
          output as a draft to check against what was actually said, not a record to trust blindly.
        </p>
      </header>

      <main className="grid gap-6 px-8 py-8 lg:grid-cols-2">
        <form onSubmit={submit} className="space-y-3">
          <label className="text-sm font-medium">Transcript</label>
          <textarea
            value={transcript}
            onChange={(e) => setTranscript(e.target.value)}
            rows={16}
            placeholder="Paste the meeting transcript here…"
            className="w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
          />
          <button
            type="submit"
            disabled={isPending || !transcript.trim()}
            className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {isPending ? "Summarizing…" : "Generate summary"}
          </button>
          {error && (
            <p className="rounded-sm bg-[var(--clay-red-soft)] p-3 text-sm text-[var(--clay-red)]">
              {error.message}
            </p>
          )}
        </form>

        <div>
          {data ? (
            <div className="space-y-4">
              <section className="rounded-sm border border-[var(--rule)] bg-white p-4">
                <h2 className="font-display text-lg">Summary</h2>
                <p className="mt-2 text-sm">{data.summary}</p>
              </section>
              <section className="rounded-sm border border-[var(--rule)] bg-white p-4">
                <h2 className="font-display text-lg">Decisions</h2>
                {data.decisions.length === 0 ? (
                  <p className="mt-2 text-sm text-[var(--ink-soft)]">None identified.</p>
                ) : (
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                    {data.decisions.map((d, i) => <li key={i}>{d}</li>)}
                  </ul>
                )}
              </section>
              <section className="rounded-sm border border-[var(--rule)] bg-white p-4">
                <h2 className="font-display text-lg">Action items</h2>
                {data.action_items.length === 0 ? (
                  <p className="mt-2 text-sm text-[var(--ink-soft)]">None identified.</p>
                ) : (
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                    {data.action_items.map((a, i) => <li key={i}>{a}</li>)}
                  </ul>
                )}
              </section>
            </div>
          ) : (
            <div className="flex h-full items-center justify-center rounded-sm border border-dashed border-[var(--rule)] p-10 text-center text-sm text-[var(--ink-soft)]">
              The summary will appear here.
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
