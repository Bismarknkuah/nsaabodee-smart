"use client";

import Link from "next/link";

/**
 * The dashboard's visual language, in one place — "a physical ledger
 * book of record, not a SaaS dashboard" (the same concept this whole
 * app is already built on), carried through to the dashboards
 * properly instead of falling back to flat colored KPI blocks. A
 * KpiTile now reads like a printed ledger line — a thin rule, a serif
 * numeral, a small-caps label — not a UI badge. Every number that
 * reaches these components is still the same real, tested backend
 * data as before; nothing here decorates with anything invented.
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
    <div className="relative overflow-hidden bg-white px-4 py-3" style={{ borderTop: `2px solid ${c}` }}>
      {icon && (
        <span className="pointer-events-none absolute -right-1 -top-1 opacity-[0.09]" style={{ color: c }}>
          <span className="block scale-[2.6]">{icon}</span>
        </span>
      )}
      <p className="font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-[var(--ink-soft)]">{label}</p>
      <p className="font-display mt-1 text-[1.7rem] leading-none text-[var(--ink)]">{value}</p>
    </div>
  );
}

/**
 * A "folio" — one panel of the ledger page. The printed-heading strip
 * (small caps, a hairline rule beneath, an accent-colored folio mark)
 * replaces the old solid-color left border; it reads as a page
 * section, not a UI card chrome.
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
    <section className="border border-[var(--rule)] bg-white">
      <div className="flex items-baseline gap-3 border-b border-[var(--rule)] px-5 py-4">
        <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: c }} aria-hidden />
        <div>
          {eyebrow && <p className="font-mono text-[10px] font-medium uppercase tracking-[0.16em] text-[var(--ink-soft)]">{eyebrow}</p>}
          <h2 className="font-display text-xl leading-tight">{title}</h2>
        </div>
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

/** A quiet, ledger-appropriate call-to-action link — used instead of filled buttons for secondary navigation, so the page keeps a printed-register feel rather than a button-heavy app feel. */
export function FolioLink({ href, children, tone = "default" }: { href: string; children: React.ReactNode; tone?: "default" | "urgent" }) {
  return (
    <Link
      href={href}
      className={`inline-flex items-center gap-1.5 border px-3 py-1.5 font-mono text-[11px] font-medium uppercase tracking-wide transition-colors ${
        tone === "urgent"
          ? "border-[var(--clay-red)] text-[var(--clay-red)] hover:bg-[var(--clay-red)] hover:text-white"
          : "border-[var(--ink)] text-[var(--ink)] hover:bg-[var(--ink)] hover:text-white"
      }`}
    >
      {children}
    </Link>
  );
}
