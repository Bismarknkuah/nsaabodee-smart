"use client";

export interface Jurisdiction { is_collector: boolean; grants: { kind: string; scope: string; family_id: string | null; label: string }[] }

/**
 * "Each one should collect in his jurisdiction only." Every collector's
 * dashboard opens with exactly what they may take, and where — so the
 * rule is visible up front, not discovered when a payment is refused.
 */
export function JurisdictionBanner({ jurisdiction }: { jurisdiction?: Jurisdiction }) {
  if (!jurisdiction) return null;
  return (
    <div className="rounded-[var(--radius)] bg-[var(--card)] p-4" style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}>
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-soft)]">Your jurisdiction</p>
      {jurisdiction.is_collector ? (
        <ul className="mt-1.5 space-y-1 text-sm">
          {jurisdiction.grants.map((g, i) => <li key={i} className="flex items-start gap-2"><span aria-hidden style={{ color: "var(--forest)" }}>✓</span><span>You collect <strong>{g.label}</strong>.</span></li>)}
        </ul>
      ) : (
        <p className="mt-1 text-sm text-[var(--text-soft)]">Your role does not receive or record money.</p>
      )}
      <p className="mt-2 text-xs text-[var(--text-soft)]">Anything outside this is refused at the ledger, for you and for everyone else.</p>
    </div>
  );
}
