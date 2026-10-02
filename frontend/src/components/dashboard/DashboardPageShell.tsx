"use client";

import { useAuthStore } from "@/store/authStore";

/**
 * The header every dashboard opens with. Same prop API as before
 * (folio, register, title, subtitle) so no caller needed changing —
 * only the presentation moved from a printed ledger masthead to a
 * clean SaaS page header: a white bar, a quiet breadcrumb-style
 * eyebrow, a bold sans-serif title.
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
    <div className="font-body min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="border-b border-[var(--border)] bg-[var(--card)] px-6 py-6 sm:px-10">
        <div className="mx-auto flex max-w-6xl items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-soft)]">
              {folio} · {register}
            </p>
            <h1 className="mt-1 text-3xl font-semibold leading-tight tracking-tight">{title}</h1>
            <p className="mt-2 max-w-xl text-sm text-[var(--text-soft)]">{subtitle}</p>
          </div>
          <div className="hidden shrink-0 text-right sm:block">
            <p className="text-xs uppercase tracking-wide text-[var(--text-soft)]">{today}</p>
            {user?.username && <p className="mt-1 text-sm font-medium">{user.username}</p>}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-8 sm:px-10">
        <div className="grid gap-6 lg:grid-cols-2">{children}</div>
      </main>
    </div>
  );
}
