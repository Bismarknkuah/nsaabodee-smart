"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import Link from "next/link";
import { useInactiveMembers } from "@/lib/hooks/useAiFeatures";
import { KpiTile } from "@/components/dashboard/DashboardVisuals";
import { IconPeople, IconWarning } from "@/components/icons/DashboardIcons";

export default function InactiveMembersPage() {
  const [days, setDays] = useState(180);
  const { data, isLoading } = useInactiveMembers(days);

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-[var(--ink-soft)]">Community Administration</p>
        <h1 className="font-display mt-1 text-4xl">Inactive Members</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Members still marked active in the roster, but with no contribution payment and no
          recorded funeral attendance in the selected window. A real query over real activity —
          not a prediction, just a fact worth a follow-up call.
        </p>
      </header>

      <main className="px-8 py-8">
        <div className="grid grid-cols-2 gap-px border border-[var(--rule)] bg-[var(--rule)] sm:max-w-md">
          <KpiTile label="Matching this window" value={data?.length ?? 0} color="clay" icon={<IconWarning />} />
          <div className="bg-white px-4 py-3">
            <p className="font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--ink-soft)]">Inactive for at least</p>
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="mt-1 w-full border-0 bg-transparent font-display text-lg outline-none"
            >
              <option value={90}>90 days</option>
              <option value={180}>180 days</option>
              <option value={365}>1 year</option>
            </select>
          </div>
        </div>

        <div className="mt-6">
          {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
          {data?.length === 0 && (
            <div className="border border-dashed border-[var(--rule)] px-6 py-10 text-center">
              <p className="font-display text-lg">Nobody matches this window</p>
            </div>
          )}
          <ol className="divide-y divide-[var(--rule)] border-y border-[var(--rule)]">
            {data?.map((m, i) => (
              <li key={m.member_id}>
                <Link href={`/members/${m.member_id}`} className="flex items-center gap-3 px-1 py-3 hover:bg-white">
                  <span className="font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(2, "0")}</span>
                  <div className="flex-1">
                    <p className="font-medium">{m.full_name}</p>
                    <p className="font-mono text-xs text-[var(--ink-soft)]">{m.membership_number}</p>
                  </div>
                  <span className="text-xs text-[var(--ink-soft)]">
                    Registered {new Date(m.last_registered).toLocaleDateString()}
                  </span>
                </Link>
              </li>
            ))}
          </ol>
        </div>
      </main>
    </div>
  );
}
