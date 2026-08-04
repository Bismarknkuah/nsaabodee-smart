"use client";

import { useState } from "react";
import { useFamilies } from "@/lib/hooks/useFamilies";
import { useCreateFuneral } from "@/lib/hooks/useFunerals";
import { formatCedis } from "@/lib/formatCedis";

export function CreateFuneralDialog({ onClose }: { onClose: () => void }) {
  const { data: families } = useFamilies(false);
  const { mutate, isPending, error } = useCreateFuneral();

  const [deceasedName, setDeceasedName] = useState("");
  const [gender, setGender] = useState<"male" | "female">("male");
  const [familyId, setFamilyId] = useState("");
  const [dateOfDeath, setDateOfDeath] = useState("");
  const [collectionStart, setCollectionStart] = useState("");
  const [overrideRate, setOverrideRate] = useState("");

  const family = families?.find((f) => f.id === familyId);
  const hasStandingRate = Boolean(family?.standing_family_rate);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!deceasedName || !familyId || !dateOfDeath || !collectionStart) return;
    mutate(
      {
        deceased_name: deceasedName,
        deceased_gender: gender,
        deceased_family_id: familyId,
        date_of_death: dateOfDeath,
        collection_start_date: collectionStart,
        own_family_amount: !hasStandingRate ? overrideRate || undefined : undefined,
      },
      { onSuccess: onClose }
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="font-body w-full max-w-lg rounded-sm bg-[var(--surface)] p-6 text-[var(--ink)] shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <h2 className="font-display text-xl">Record a funeral</h2>
          <button onClick={onClose} className="text-[var(--ink-soft)] hover:text-[var(--ink)]" aria-label="Close">
            ✕
          </button>
        </div>
        <p className="mt-1 text-sm text-[var(--ink-soft)]">
          Every active member is added to this funeral&apos;s ledger automatically the
          moment you save it — nobody needs to be registered by hand.
        </p>

        <form onSubmit={submit} className="mt-4 space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
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
                value={gender}
                onChange={(e) => setGender(e.target.value as "male" | "female")}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
              >
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">Date of death</label>
              <input
                type="date"
                value={dateOfDeath}
                onChange={(e) => setDateOfDeath(e.target.value)}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
              />
            </div>
          </div>

          <div>
            <label className="text-sm font-medium">Family</label>
            <select
              value={familyId}
              onChange={(e) => setFamilyId(e.target.value)}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            >
              <option value="">Choose the deceased&apos;s family…</option>
              {families?.filter((f) => f.status === "active").map((f) => (
                <option key={f.id} value={f.id}>{f.name}</option>
              ))}
            </select>
          </div>

          {familyId && (
            <div className="rounded-sm bg-white p-3 text-sm">
              {hasStandingRate ? (
                <p>
                  Members of <strong>{family?.name}</strong> will pay its approved rate of{" "}
                  <strong>{formatCedis(family!.standing_family_rate!)}</strong>. Everyone else pays
                  the community&apos;s general rate by gender.
                </p>
              ) : (
                <div>
                  <p className="text-[var(--clay-red)]">
                    <strong>{family?.name}</strong> has no approved contribution rate yet. Set a
                    one-off amount for this funeral only, or approve a standing rate for this
                    family first.
                  </p>
                  <label className="mt-2 block text-sm font-medium">Amount for this funeral (GH₵)</label>
                  <input
                    type="number"
                    min="0.01"
                    step="0.01"
                    value={overrideRate}
                    onChange={(e) => setOverrideRate(e.target.value)}
                    className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
                  />
                </div>
              )}
            </div>
          )}

          <div>
            <label className="text-sm font-medium">Contribution collection starts</label>
            <input
              type="date"
              value={collectionStart}
              onChange={(e) => setCollectionStart(e.target.value)}
              className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
          </div>

          {error && <p className="text-sm text-[var(--clay-red)]">{error.message}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-3 py-2 text-sm text-[var(--ink-soft)]">
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {isPending ? "Creating…" : "Create funeral & open ledger"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
