"use client";

import { useState } from "react";
import { useAttendance, useAttendanceSummary, useFuneralLogisticsActions } from "@/lib/hooks/useFuneralLogistics";
import { membersApi } from "@/lib/api/members";
import { useQuery } from "@tanstack/react-query";

export function AttendancePanel({ funeralId }: { funeralId: string }) {
  const { data: records, isLoading } = useAttendance(funeralId);
  const { data: summary } = useAttendanceSummary(funeralId);
  const { recordAttendance } = useFuneralLogisticsActions(funeralId);

  const [memberQuery, setMemberQuery] = useState("");
  const [guestName, setGuestName] = useState("");
  const { data: memberResults } = useQuery({
    queryKey: ["attendance-member-search", memberQuery],
    queryFn: () => membersApi.list({ search: memberQuery }),
    enabled: memberQuery.trim().length >= 2,
  });

  return (
    <section className="mt-6 rounded-sm border border-[var(--forest)] bg-white p-5">
      <h2 className="font-display text-xl" style={{ color: "var(--forest)" }}>Attendance</h2>
      {summary && (
        <p className="mt-1 text-sm text-[var(--ink-soft)]">
          {summary.members_attended} of {summary.obligated_member_count} members attended · {summary.guests_attended} guest(s)
        </p>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <div className="rounded-sm bg-[var(--forest-soft)] p-3">
          <label className="text-xs font-medium text-[var(--forest)]">Check in a member</label>
          <input
            value={memberQuery}
            onChange={(e) => setMemberQuery(e.target.value)}
            placeholder="Search by name…"
            className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
          />
          {memberResults && memberResults.length > 0 && (
            <ul className="mt-2 max-h-32 divide-y divide-[var(--rule)] overflow-y-auto rounded-sm bg-white">
              {memberResults.map((m) => (
                <li key={m.id}>
                  <button
                    onClick={() => { recordAttendance.mutate({ member_id: m.id }); setMemberQuery(""); }}
                    className="w-full px-3 py-2 text-left text-sm hover:bg-[var(--surface)]"
                  >
                    {m.full_name}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="rounded-sm bg-[var(--surface)] p-3">
          <label className="text-xs font-medium">Log a guest by name</label>
          <div className="mt-1 flex gap-2">
            <input
              value={guestName}
              onChange={(e) => setGuestName(e.target.value)}
              className="flex-1 rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
            />
            <button
              onClick={() => { if (guestName.trim()) { recordAttendance.mutate({ guest_name: guestName.trim() }); setGuestName(""); } }}
              className="rounded-sm bg-[var(--forest)] px-3 py-2 text-sm font-medium text-white"
            >
              Add
            </button>
          </div>
        </div>
      </div>

      <ul className="mt-4 max-h-48 divide-y divide-[var(--rule)] overflow-y-auto">
        {isLoading && <li className="py-2 text-sm text-[var(--ink-soft)]">Loading…</li>}
        {records?.map((r) => (
          <li key={r.id} className="py-2 text-sm">
            {r.display_name} {!r.member && <span className="text-xs text-[var(--ink-soft)]">(guest)</span>}
          </li>
        ))}
      </ul>
    </section>
  );
}
