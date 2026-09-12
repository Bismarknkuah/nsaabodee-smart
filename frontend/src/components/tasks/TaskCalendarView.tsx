"use client";

import { useState } from "react";
import type { MemberTask } from "@/types/task";

const STATUS_ACCENT: Record<string, string> = {
  pending: "var(--gold)", in_progress: "var(--violet)", pending_approval: "var(--clay-red)", done: "var(--forest)",
};

function startOfMonth(d: Date) { return new Date(d.getFullYear(), d.getMonth(), 1); }
function daysInMonth(d: Date) { return new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate(); }

/** A real month grid, not a list with dates printed next to it — tasks with a due date land on the actual day. */
export function TaskCalendarView({ tasks }: { tasks: MemberTask[] }) {
  const [cursor, setCursor] = useState(() => startOfMonth(new Date()));
  const [selectedDay, setSelectedDay] = useState<string | null>(null);

  const firstWeekday = cursor.getDay();
  const totalDays = daysInMonth(cursor);
  const byDay = new Map<string, MemberTask[]>();
  for (const t of tasks) {
    if (!t.due_date) continue;
    const key = t.due_date;
    if (!byDay.has(key)) byDay.set(key, []);
    byDay.get(key)!.push(t);
  }

  const cells: (number | null)[] = [...Array(firstWeekday).fill(null), ...Array.from({ length: totalDays }, (_, i) => i + 1)];
  const dateKey = (day: number) => new Date(cursor.getFullYear(), cursor.getMonth(), day).toISOString().slice(0, 10);
  const monthLabel = cursor.toLocaleDateString(undefined, { month: "long", year: "numeric" });
  const undated = tasks.filter((t) => !t.due_date);

  return (
    <div>
      <div className="flex items-center justify-between">
        <button onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() - 1, 1))} className="rounded-sm border border-[var(--rule)] px-3 py-1 text-sm hover:border-[var(--ink)]">←</button>
        <p className="font-display text-lg">{monthLabel}</p>
        <button onClick={() => setCursor(new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1))} className="rounded-sm border border-[var(--rule)] px-3 py-1 text-sm hover:border-[var(--ink)]">→</button>
      </div>

      <div className="mt-3 grid grid-cols-7 gap-px border border-[var(--rule)] bg-[var(--rule)] text-center font-mono text-[10px] uppercase text-[var(--ink-soft)]">
        {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((d) => <div key={d} className="bg-[var(--surface)] py-1">{d}</div>)}
      </div>
      <div className="grid grid-cols-7 gap-px border-x border-b border-[var(--rule)] bg-[var(--rule)]">
        {cells.map((day, i) => {
          const key = day ? dateKey(day) : null;
          const dayTasks = key ? byDay.get(key) ?? [] : [];
          return (
            <button
              key={i}
              disabled={!day}
              onClick={() => key && setSelectedDay(key === selectedDay ? null : key)}
              className="min-h-[4.5rem] bg-white p-1 text-left align-top disabled:bg-[var(--paper)]"
              style={{ outline: key === selectedDay ? "2px solid var(--forest)" : "none" }}
            >
              {day && <span className="text-xs text-[var(--ink-soft)]">{day}</span>}
              <div className="mt-1 space-y-0.5">
                {dayTasks.slice(0, 3).map((t) => (
                  <div key={t.id} className="truncate rounded-sm px-1 text-[10px] text-white" style={{ backgroundColor: STATUS_ACCENT[t.status] }}>
                    {t.title}
                  </div>
                ))}
                {dayTasks.length > 3 && <p className="text-[9px] text-[var(--ink-soft)]">+{dayTasks.length - 3} more</p>}
              </div>
            </button>
          );
        })}
      </div>

      {selectedDay && (
        <div className="mt-4 rounded-sm border border-[var(--rule)] bg-[var(--surface)] p-3">
          <p className="font-mono text-[10px] uppercase tracking-wide text-[var(--ink-soft)]">{new Date(selectedDay).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}</p>
          <ul className="mt-2 space-y-2">
            {(byDay.get(selectedDay) ?? []).map((t) => (
              <li key={t.id} className="rounded-sm border border-[var(--rule)] bg-white p-2 text-sm">
                <p className="font-medium">{t.title}</p>
                <p className="text-xs text-[var(--ink-soft)]">{t.assigned_to_name} · {t.status.replace(/_/g, " ")}</p>
              </li>
            ))}
          </ul>
        </div>
      )}

      {undated.length > 0 && (
        <div className="mt-4">
          <p className="font-mono text-[10px] uppercase tracking-wide text-[var(--ink-soft)]">No due date ({undated.length})</p>
          <ul className="mt-2 divide-y divide-[var(--rule)]">
            {undated.map((t) => <li key={t.id} className="py-1.5 text-sm">{t.title} <span className="text-xs text-[var(--ink-soft)]">— {t.assigned_to_name}</span></li>)}
          </ul>
        </div>
      )}
    </div>
  );
}
