"use client";

import "@/styles/family-registry-tokens.css";
import Link from "next/link";
import { useState } from "react";
import { useMembers } from "@/lib/hooks/useMembers";
import { useFuzzySearch } from "@/lib/hooks/useAiFeatures";
import { RegisterMemberDialog } from "@/components/members/RegisterMemberDialog";
import type { DefaulterTier } from "@/types/member";

const TIER_COLOR: Record<DefaulterTier, string> = {
  none: "var(--forest)",
  warning: "var(--gold)",
  high_warning: "var(--gold)",
  flagged: "var(--clay-red)",
};

const TIER_LABEL: Record<DefaulterTier, string> = {
  none: "In good standing",
  warning: "Warning",
  high_warning: "High warning",
  flagged: "Flagged",
};

export default function MembersPage() {
  const [search, setSearch] = useState("");
  const { data: members, isLoading } = useMembers({ search });
  const [showRegister, setShowRegister] = useState(false);
  const showFuzzy = search.trim().length >= 2 && !isLoading && (members?.length ?? 0) === 0;
  const { data: fuzzyResults } = useFuzzySearch(showFuzzy ? search : "");

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-6 py-6 sm:px-10">
        <div className="mx-auto flex max-w-6xl items-end justify-between gap-4">
          <div>
            <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
              Community Register · {members?.length ?? 0} listed
            </p>
            <h1 className="font-display mt-1 text-4xl">Members</h1>
          </div>
          <div className="flex gap-2">
            <Link
              href="/members/defaulters"
              className="border border-[var(--clay-red)] px-4 py-2 text-sm font-medium text-[var(--clay-red)] hover:bg-[var(--clay-red-soft)]"
            >
              Defaulters
            </Link>
            <button
              onClick={() => setShowRegister(true)}
              className="bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              Register member
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-6 py-5 sm:px-10">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search by name, phone, or Ghana Card…"
          className="w-full max-w-md border-0 border-b-2 border-[var(--rule)] bg-transparent px-0 py-2 text-sm outline-none focus:border-[var(--forest)] sm:w-80"
        />
      </div>

      <main className="mx-auto max-w-6xl px-6 pb-16 sm:px-10">
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading members…</p>}

        {showFuzzy && fuzzyResults && fuzzyResults.length > 0 && (
          <div className="mb-4 border border-dashed border-[var(--rule)] bg-white p-4">
            <p className="font-mono text-[11px] font-medium uppercase tracking-wide text-[var(--ink-soft)]">
              No exact match — did you mean
            </p>
            <ul className="mt-2 space-y-1">
              {fuzzyResults.map((r) => (
                <li key={r.member_id}>
                  <Link
                    href={`/members/${r.member_id}`}
                    className="text-sm text-[var(--forest)] hover:underline"
                  >
                    {r.full_name} <span className="font-mono text-xs text-[var(--ink-soft)]">({r.membership_number})</span>
                  </Link>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-[var(--ink-soft)]">
              Fuzzy text matching, not speech recognition — if you spoke this search aloud, your
              device&apos;s own dictation turned it into text first.
            </p>
          </div>
        )}

        <ul className="divide-y divide-[var(--rule)] border-y-2 border-[var(--ink)]">
          {members?.map((m, i) => (
            <li key={m.id}>
              <Link href={`/members/${m.id}`} className="flex items-center gap-4 py-3.5 hover:bg-white">
                <span className="w-8 shrink-0 font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(3, "0")}</span>
                {m.photo_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={m.photo_url} alt="" className="h-10 w-10 rounded-full object-cover" />
                ) : (
                  <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--surface)] font-display text-sm text-[var(--ink-soft)]">
                    {m.full_name.charAt(0)}
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="font-medium">{m.full_name}</p>
                  <p className="font-mono text-xs text-[var(--ink-soft)]">
                    {m.membership_number} · {m.family_detail?.name ?? "No family"}
                  </p>
                </div>
                <span className="flex items-center gap-1.5 text-xs font-medium" style={{ color: TIER_COLOR[m.defaulter_tier] }}>
                  <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: TIER_COLOR[m.defaulter_tier] }} />
                  {TIER_LABEL[m.defaulter_tier]}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </main>

      {showRegister && <RegisterMemberDialog onClose={() => setShowRegister(false)} />}
    </div>
  );
}
