"use client";

import { useFamilyUiStore } from "@/store/familyUiStore";

/**
 * "I can't scroll some of the forms down, so make it great so that I
 * can scroll them down and when filling." The actual bug: this shell
 * had no max-height or overflow at all, so a form taller than the
 * viewport (a long registration form, for instance) simply ran off
 * the bottom of the screen with no way to reach the rest of it,
 * submit button included. Fixed once here for every one of the nine
 * family dialogs built on this same shell, rather than once per
 * dialog.
 *
 * A sticky header (title, description, close button) stays visible
 * the whole time; only the middle content scrolls, its own max-height
 * capped well under the viewport so there is always visible room
 * above and below the dialog itself, on a small phone screen included.
 */
export function DialogShell({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  const closeDialog = useFamilyUiStore((s) => s.closeDialog);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        role="dialog"
        aria-modal="true"
        className="font-body flex max-h-[85vh] w-full max-w-md flex-col overflow-hidden rounded-[var(--radius)] bg-[var(--card)] text-[var(--text)]"
        style={{ boxShadow: "var(--shadow-md)" }}
      >
        <div className="shrink-0 border-b border-[var(--border-soft)] p-6 pb-4">
          <div className="flex items-start justify-between gap-4">
            <h2 className="text-xl font-semibold">{title}</h2>
            <button
              onClick={closeDialog}
              aria-label="Close"
              className="shrink-0 text-[var(--text-soft)] hover:text-[var(--text)]"
            >
              ✕
            </button>
          </div>
          {description && <p className="mt-1 text-sm text-[var(--text-soft)]">{description}</p>}
        </div>
        <div className="overflow-y-auto p-6 pt-4">{children}</div>
      </div>
    </div>
  );
}
