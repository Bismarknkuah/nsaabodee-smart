"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { funeralsApi } from "@/lib/api/funerals";
import { membersApi } from "@/lib/api/members";
import { SUGGESTED_FUNERAL_COMMITTEE_TITLES } from "@/types/funeral";

/**
 * "Every funeral creates a committee workspace... Chairman, Vice
 * Chairman, Secretary, Treasurer, Welfare Officer, Logistics Officer,
 * Food Coordinator, Transport Coordinator, Accommodation Coordinator,
 * Protocol Officer, Security Officer, PR Officer... Custom positions
 * allowed." Deliberately separate from the desk assignments panel
 * above it on this page — this is organizational recognition, not a
 * new payment-collecting authority. Appointing/removing is enforced
 * server-side (community-wide leadership, or the deceased's own
 * family Head/Secretary); this component doesn't try to guess that
 * client-side, it just shows the buttons and lets the backend decide.
 */
export function CommitteePositionsPanel({ funeralId }: { funeralId: string }) {
  const qc = useQueryClient();
  const { data: positions, isLoading } = useQuery({
    queryKey: ["committee-positions", funeralId],
    queryFn: () => funeralsApi.listCommitteePositions(funeralId),
  });

  const [query, setQuery] = useState("");
  const [title, setTitle] = useState(SUGGESTED_FUNERAL_COMMITTEE_TITLES[0]);
  const [customTitle, setCustomTitle] = useState("");
  const usingCustomTitle = title === "__custom__";

  const { data: memberResults } = useQuery({
    queryKey: ["committee-appointment-search", query],
    queryFn: () => membersApi.list({ search: query }),
    enabled: query.trim().length >= 2,
  });

  const appoint = useMutation({
    mutationFn: ({ memberId, title }: { memberId: string; title: string }) => funeralsApi.appointCommitteePosition(funeralId, memberId, title),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["committee-positions", funeralId] }),
  });
  const remove = useMutation({
    mutationFn: (positionId: string) => funeralsApi.removeCommitteePosition(funeralId, positionId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["committee-positions", funeralId] }),
  });

  return (
    <section className="mt-6 rounded-sm border border-[var(--rule)] bg-white p-5">
      <h2 className="font-display text-xl">Funeral Committee</h2>
      <p className="mt-1 text-sm text-[var(--ink-soft)]">
        Organizational recognition, not a login role or payment-collecting authority — an
        appointee&apos;s account and permissions never change because of a position recorded
        here. Visible to the whole community.
      </p>

      {isLoading && <p className="mt-2 text-sm text-[var(--ink-soft)]">Loading…</p>}
      {positions && positions.length === 0 && <p className="mt-2 text-sm text-[var(--ink-soft)]">No committee recorded yet.</p>}
      {positions && positions.length > 0 && (
        <ul className="mt-3 divide-y divide-[var(--rule)] rounded-sm border border-[var(--rule)]">
          {positions.map((p) => (
            <li key={p.id} className="flex items-center justify-between px-3 py-2 text-sm">
              <span><span className="font-medium">{p.title}</span> — {p.member_name}</span>
              <button onClick={() => remove.mutate(p.id)} disabled={remove.isPending} className="text-xs text-[var(--clay-red)] hover:underline">
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 border-t border-[var(--rule)] pt-4">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Appoint someone to the committee</p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <select
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm"
          >
            {SUGGESTED_FUNERAL_COMMITTEE_TITLES.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
            <option value="__custom__">Other — custom title…</option>
          </select>
          {usingCustomTitle && (
            <input
              value={customTitle}
              onChange={(e) => setCustomTitle(e.target.value)}
              placeholder="Custom title"
              className="rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
            />
          )}
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search a member to appoint…"
            className="flex-1 rounded-sm border border-[var(--rule)] px-3 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
          />
        </div>
        {memberResults && memberResults.length > 0 && (
          <ul className="mt-2 max-h-28 divide-y divide-[var(--rule)] overflow-y-auto rounded-sm border border-[var(--rule)]">
            {memberResults.map((m) => (
              <li key={m.id} className="flex items-center justify-between px-3 py-1.5 text-sm">
                <span>{m.full_name}</span>
                <button
                  onClick={() => {
                    const finalTitle = usingCustomTitle ? customTitle.trim() : title;
                    if (!finalTitle) return;
                    appoint.mutate({ memberId: m.id, title: finalTitle }, { onSuccess: () => { setQuery(""); setCustomTitle(""); } });
                  }}
                  disabled={appoint.isPending || (usingCustomTitle && !customTitle.trim())}
                  className="rounded-sm border border-[var(--rule)] px-2 py-1 text-xs font-medium hover:border-[var(--forest)] hover:text-[var(--forest)] disabled:opacity-50"
                >
                  Appoint
                </button>
              </li>
            ))}
          </ul>
        )}
        {appoint.isError && <p className="mt-1 text-xs text-[var(--clay-red)]">{appoint.error.message}</p>}
      </div>
    </section>
  );
}
