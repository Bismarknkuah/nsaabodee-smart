/**
 * Shared building blocks for data-entry forms across the platform.
 * "Modernize the data entry forms so that all will be user friendly."
 *
 * Every existing form already repeats the same label-above-input
 * shape and the same "eyebrow" section-label style already used
 * elsewhere on this platform (see e.g. the "COMMUNITY REGISTER · n"
 * label above the Members page's own title) — these two components
 * give that established language a single, consistent home instead
 * of retyping the same className string in every field of every
 * form. A ledger book's own convention: related entries are grouped
 * under a clear heading, separated by a hairline rule, not left as
 * one undifferentiated block.
 */

export function FormSection({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="border-t border-[var(--border-soft)] pt-4 first:border-t-0 first:pt-0">
      <p className="text-xs font-semibold uppercase tracking-wide text-[var(--text-soft)]">
        {label}
      </p>
      {hint && <p className="mt-0.5 text-xs text-[var(--text-soft)]">{hint}</p>}
      <div className="mt-3 grid grid-cols-2 gap-3">{children}</div>
    </div>
  );
}

export function Field({
  label,
  hint,
  wide = false,
  children,
}: {
  label: string;
  hint?: string;
  /** Spans both columns of the enclosing FormSection grid — for a full name, an address, anything that reads awkwardly at half width. */
  wide?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={wide ? "col-span-2" : undefined}>
      <label className="text-sm font-medium text-[var(--text)]">{label}</label>
      <div className="mt-1">{children}</div>
      {hint && <p className="mt-1 text-xs text-[var(--text-soft)]">{hint}</p>}
    </div>
  );
}

/**
 * The one, consistent input/select/textarea treatment every form on
 * this platform should share — rounded corners and a soft indigo
 * focus ring, matching the SaaS card system the rest of the dashboard
 * now uses.
 */
export const FIELD_INPUT_CLASS =
  "w-full rounded-lg border border-[var(--border)] bg-white px-3 py-2 text-sm text-[var(--text)] outline-none transition-shadow focus:border-[var(--primary)] focus:ring-2 focus:ring-[var(--primary)]/15";
