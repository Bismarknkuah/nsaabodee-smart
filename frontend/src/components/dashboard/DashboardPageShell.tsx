"use client";

import { useAuthStore } from "@/store/authStore";

/**
 * The ledger masthead every dashboard opens with — a running header
 * in the same spirit as a printed register's title page: a folio
 * mark, the section name, who's holding it, and today's date. Each
 * role passes its own folio number and register name, so the ten
 * dashboards read as ten sections of one book, not ten copies of one
 * template with different words swapped in.
 */
export function DashboardPageShell({
  folio, register, title, subtitle, children,
}: {
  folio: string;
  register: string;
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  const user = useAuthStore((s) => s.user);
  const today = new Date().toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" });

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-6 py-6 sm:px-10">
        <div className="mx-auto flex max-w-6xl items-start justify-between gap-4">
          <div>
            <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
              {folio} · {register}
            </p>
            <h1 className="font-display mt-1 text-4xl leading-tight">{title}</h1>
            <p className="mt-2 max-w-xl text-sm text-[var(--ink-soft)]">{subtitle}</p>
          </div>
          <div className="hidden shrink-0 text-right sm:block">
            <p className="font-mono text-[11px] uppercase tracking-wide text-[var(--ink-soft)]">{today}</p>
            {user?.username && <p className="font-display mt-1 text-sm">{user.username}</p>}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8 sm:px-10">
        <div className="grid gap-6 lg:grid-cols-2">{children}</div>
      </main>
    </div>
  );
}
