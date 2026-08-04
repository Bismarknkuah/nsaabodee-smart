"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { memorialApi } from "@/lib/api/memorial";
import { formatCedis } from "@/lib/formatCedis";

/**
 * The one page in this entire app that deliberately requires no login
 * at all — a link anyone can be sent, whether they're a registered
 * member or not. Uses the same brand identity as the public homepage
 * (navy + gold), not the internal app's own working theme, since this
 * is squarely on the public-facing side of that line.
 */
export default function MemorialPage() {
  const params = useParams();
  const funeralId = params.funeralId as string;
  const qc = useQueryClient();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["memorial", funeralId],
    queryFn: () => memorialApi.get(funeralId),
    enabled: Boolean(funeralId),
    retry: false,
  });

  const [authorName, setAuthorName] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const submitTribute = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setSubmitError(null);
    try {
      await memorialApi.submitTribute(funeralId, authorName, message);
      setSubmitted(true);
      setAuthorName("");
      setMessage("");
      qc.invalidateQueries({ queryKey: ["memorial", funeralId] });
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "Could not submit your tribute.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="nb-memorial min-h-screen">
      <style>{`
        .nb-memorial {
          --nb-navy: #0f2745;
          --nb-navy-deep: #081627;
          --nb-gold: #c9a227;
          --nb-gold-soft: #f2e6bf;
          --nb-cream: #f7f8fa;
          --nb-ink: #1a2433;
          --nb-ink-soft: #5b6675;
          font-family: "Inter", system-ui, sans-serif;
          color: var(--nb-ink);
          background: var(--nb-cream);
        }
        .nb-memorial h1, .nb-memorial h2, .nb-memorial .nb-display {
          font-family: "Fraunces", Georgia, serif;
        }
      `}</style>

      {isLoading && (
        <div className="flex min-h-screen items-center justify-center">
          <p className="text-sm text-[var(--nb-ink-soft)]">Loading…</p>
        </div>
      )}

      {(isError || (!isLoading && data === null)) && (
        <div className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
          <p className="nb-display text-2xl">This page isn&apos;t available</p>
          <p className="mt-2 max-w-sm text-sm text-[var(--nb-ink-soft)]">
            There&apos;s no published memorial page here — check the link, or it may not
            have been made public yet.
          </p>
        </div>
      )}

      {data && (
        <>
          <header className="bg-[var(--nb-navy)] px-6 py-16 text-center sm:px-10">
            {data.photo_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={data.photo_url} alt="" className="mx-auto h-32 w-32 rounded-full border-4 border-[var(--nb-gold)] object-cover" />
            )}
            <p className="mt-6 font-mono text-xs uppercase tracking-[0.3em] text-[var(--nb-gold)]">In Loving Memory</p>
            <h1 className="nb-display mt-3 text-4xl text-white sm:text-5xl">{data.deceased_name}</h1>
            <p className="mt-3 text-sm text-white/60">
              {data.date_of_death && new Date(data.date_of_death).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}
              {data.funeral_date && ` · Funeral: ${new Date(data.funeral_date).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" })}`}
            </p>
          </header>

          <main className="mx-auto max-w-2xl px-6 py-14 sm:px-10">
            {data.tribute_message && (
              <p className="nb-display text-center text-xl leading-relaxed text-[var(--nb-ink)]">&ldquo;{data.tribute_message}&rdquo;</p>
            )}

            {data.contribution_total && (
              <p className="mt-8 text-center text-sm text-[var(--nb-ink-soft)]">
                Total contributions so far: <span className="font-medium text-[var(--nb-navy)]">{formatCedis(data.contribution_total)}</span>
              </p>
            )}

            {data.payout_accounts.length > 0 && (
              <section className="mt-10 rounded-sm border border-[var(--nb-gold)] bg-[var(--nb-gold-soft)] p-6">
                <h3 className="nb-display text-lg text-[var(--nb-navy)]">How to contribute</h3>
                <ul className="mt-3 space-y-2">
                  {data.payout_accounts.map((a, i) => (
                    <li key={i} className="text-sm">
                      <span className="font-medium">{a.provider_name}</span> — {a.account_number}
                      <span className="text-[var(--nb-ink-soft)]"> ({a.account_holder_name})</span>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section className="mt-14">
              <h2 className="nb-display text-2xl">Tributes</h2>
              {data.tributes.length === 0 ? (
                <p className="mt-3 text-sm text-[var(--nb-ink-soft)]">Be the first to leave a tribute below.</p>
              ) : (
                <ul className="mt-5 space-y-4">
                  {data.tributes.map((t, i) => (
                    <li key={i} className="rounded-sm border border-black/10 bg-white p-5">
                      <p className="text-sm leading-relaxed">{t.message}</p>
                      <p className="mt-2 text-xs font-medium text-[var(--nb-ink-soft)]">
                        — {t.author_name}, {new Date(t.created_at).toLocaleDateString()}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="mt-10 rounded-sm border border-black/10 bg-white p-6">
              <h3 className="nb-display text-lg">Leave a tribute</h3>
              {submitted ? (
                <p className="mt-3 text-sm" style={{ color: "var(--nb-navy)" }}>
                  Thank you — your tribute will appear once it&apos;s been reviewed.
                </p>
              ) : (
                <form onSubmit={submitTribute} className="mt-3 space-y-3">
                  <input
                    value={authorName}
                    onChange={(e) => setAuthorName(e.target.value)}
                    placeholder="Your name"
                    className="w-full rounded-sm border border-black/10 px-3 py-2 text-sm outline-none focus:border-[var(--nb-navy)]"
                  />
                  <textarea
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder="Your message"
                    rows={3}
                    className="w-full rounded-sm border border-black/10 px-3 py-2 text-sm outline-none focus:border-[var(--nb-navy)]"
                  />
                  {submitError && <p className="text-xs text-red-600">{submitError}</p>}
                  <button
                    type="submit"
                    disabled={submitting || !authorName.trim() || !message.trim()}
                    className="rounded-sm bg-[var(--nb-navy)] px-5 py-2 text-sm font-medium text-white disabled:opacity-60"
                  >
                    {submitting ? "Submitting…" : "Submit tribute"}
                  </button>
                </form>
              )}
            </section>
          </main>

          <footer className="border-t border-black/5 py-8 text-center text-xs text-[var(--nb-ink-soft)]">
            Nsaabodeɛ Smart
          </footer>
        </>
      )}
    </div>
  );
}
