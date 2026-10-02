"use client";

import Link from "next/link";

/**
 * The dashboard's visual language, in one place. "Can we make it a
 * SaaS dashboard, since we have a platform admin who manages all the
 * community admins and the system is also a tenant system?" — a
 * genuine, deliberate direction change from the person. A KpiTile now
 * reads like a real SaaS stat card: a rounded white surface, a subtle
 * shadow, a colored icon badge, a large bold number, not a printed
 * ledger line. Every number that reaches these components is still
 * the same real, tested backend data as before; only the presentation
 * changed.
 *
 * TrendChart lives in its own file (TrendChart.tsx) deliberately — it's
 * the only piece here that needs recharts, and pages that only use
 * KpiTile/SectionCard/FolioLink shouldn't pay for that dependency.
 */

const ACCENT = {
  forest: "var(--forest)",
  gold: "var(--gold)",
  clay: "var(--clay-red)",
  violet: "var(--violet)",
} as const;

export function KpiTile({
  label, value, color = "forest", icon,
}: {
  label: string;
  value: string | number;
  color?: keyof typeof ACCENT;
  icon?: React.ReactNode;
}) {
  const c = ACCENT[color];
  return (
    <div
      className="rounded-[var(--radius)] bg-[var(--card)] p-4"
      style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-[var(--text-soft)]">{label}</p>
        {icon && (
          <span
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg"
            style={{ backgroundColor: `color-mix(in srgb, ${c} 12%, white)`, color: c }}
          >
            {icon}
          </span>
        )}
      </div>
      <p className="mt-2 text-2xl font-semibold leading-none text-[var(--text)]">{value}</p>
    </div>
  );
}

/**
 * A section of the dashboard — a clean, rounded white card with a
 * colored accent dot next to its own heading, replacing the old
 * ledger-page "folio" strip.
 */
export function SectionCard({
  title, accent = "forest", eyebrow, children,
}: {
  title: string;
  accent?: keyof typeof ACCENT;
  eyebrow?: string;
  children: React.ReactNode;
}) {
  const c = ACCENT[accent];
  return (
    <section
      className="overflow-hidden rounded-[var(--radius)] bg-[var(--card)]"
      style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}
    >
      <div className="flex items-baseline gap-3 border-b border-[var(--border-soft)] px-5 py-4">
        <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: c }} aria-hidden />
        <div>
          {eyebrow && <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-soft)]">{eyebrow}</p>}
          <h2 className="text-lg font-semibold leading-tight text-[var(--text)]">{title}</h2>
        </div>
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

/** A quiet, secondary call-to-action link — a rounded pill in the outline style common to SaaS dashboards, used instead of a filled button so the page keeps clear visual hierarchy. */
export function FolioLink({ href, children, tone = "default" }: { href: string; children: React.ReactNode; tone?: "default" | "urgent" }) {
  return (
    <Link
      href={href}
      className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
        tone === "urgent"
          ? "border-[var(--clay-red)] text-[var(--clay-red)] hover:bg-[var(--clay-red)] hover:text-white"
          : "border-[var(--primary)] text-[var(--primary)] hover:bg-[var(--primary)] hover:text-white"
      }`}
    >
      {children}
    </Link>
  );
}
