"use client";

import { useState } from "react";
import { useRequestFuneralOpening } from "@/lib/hooks/useFunerals";
import { useAuthStore } from "@/store/authStore";

/**
 * "Is the family head who will open the ledger when there's a
 * funeral." A Family Head doesn't pick which family — they don't need
 * to, it's always their own — so this form is deliberately shorter than
 * the direct-creation one an admin uses. Submitting creates a
 * PENDING_APPROVAL funeral: nobody is billed until two of
 * {Secretary, Chairman, Community Admin} approve it (see the Pending
 * Approval tab on the funerals list).
 */
export function RequestFuneralOpeningDialog({ onClose }: { onClose: () => void }) {
  const user = useAuthStore((s) => s.user);
  const { mutate, isPending, error } = useRequestFuneralOpening();

  const [deceasedName, setDeceasedName] = useState("");
  const [deceasedGender, setDeceasedGender] = useState<"male" | "female">("male");
  const [dateOfDeath, setDateOfDeath] = useState("");
  const [collectionStartDate, setCollectionStartDate] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    mutate(
      {
        deceased_name: deceasedName,
        deceased_gender: deceasedGender,
        date_of_death: dateOfDeath,
        collection_start_date: collectionStartDate,
      },
      { onSuccess: onClose }
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="font-body w-full max-w-md rounded-sm bg-[var(--surface)] p-6 text-[var(--ink)] shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <h2 className="font-display text-xl">Request a funeral opening</h2>
          <button onClick={onClose} className="text-[var(--ink-soft)] hover:text-[var(--ink)]" aria-label="Close">✕</button>
        </div>
        <p className="mt-1 text-sm text-[var(--ink-soft)]">
          This opens for <strong>{user?.community_name ?? "your community"}</strong>&apos;s own
          family — nobody is billed a single cedi until two of the Secretary, Chairman, or
          Community Admin approve it.
        </p>

        <form onSubmit={submit} className="mt-4 space-y-4">
          <div>
            <label className="text-sm font-medium">Deceased&apos;s name</label>
            <input
              value={deceasedName}
              onChange={(e) => setDeceasedName(e.target.value)}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
          </div>
          <div>
            <label className="text-sm font-medium">Gender</label>
            <select
              value={deceasedGender}
              onChange={(e) => setDeceasedGender(e.target.value as "male" | "female")}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            >
              <option value="male">Male</option>
              <option value="female">Female</option>
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium">Date of death</label>
              <input
                type="date" value={dateOfDeath} onChange={(e) => setDateOfDeath(e.target.value)}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
              />
            </div>
            <div>
              <label className="text-sm font-medium">Collections start</label>
              <input
                type="date" value={collectionStartDate} onChange={(e) => setCollectionStartDate(e.target.value)}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
              />
            </div>
          </div>

          {error && <p className="text-sm text-[var(--clay-red)]">{error.message}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-3 py-2 text-sm text-[var(--ink-soft)]">Cancel</button>
            <button
              type="submit"
              disabled={isPending || !deceasedName || !dateOfDeath || !collectionStartDate}
              className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {isPending ? "Sending request…" : "Send for approval"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
