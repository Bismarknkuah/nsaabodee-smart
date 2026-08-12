"use client";

import { useFamilyUiStore } from "@/store/familyUiStore";

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
        className="font-body w-full max-w-md rounded-sm bg-[var(--surface)] p-6 text-[var(--ink)] shadow-xl"
      >
        <div className="flex items-start justify-between gap-4">
          <h2 className="font-display text-xl">{title}</h2>
          <button
            onClick={closeDialog}
            aria-label="Close"
            className="text-[var(--ink-soft)] hover:text-[var(--ink)]"
          >
            ✕
          </button>
        </div>
        {description && <p className="mt-1 text-sm text-[var(--ink-soft)]">{description}</p>}
        <div className="mt-4">{children}</div>
      </div>
    </div>
  );
}
