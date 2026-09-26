"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useFamilies } from "@/lib/hooks/useFamilies";
import { useCreateFuneral } from "@/lib/hooks/useFunerals";
import { membersApi } from "@/lib/api/members";
import { formatCedis } from "@/lib/formatCedis";
import { Field, FormSection, FIELD_INPUT_CLASS } from "@/components/forms/FormPrimitives";

export function CreateFuneralDialog({ onClose }: { onClose: () => void }) {
  const { data: families } = useFamilies(false);
  const { mutate, isPending, error } = useCreateFuneral();

  const [deceasedName, setDeceasedName] = useState("");
  const [gender, setGender] = useState<"male" | "female">("male");
  const [familyId, setFamilyId] = useState("");
  const [causeOfDeath, setCauseOfDeath] = useState("");
  const [deceasedMemberId, setDeceasedMemberId] = useState("");
  const [dateOfDeath, setDateOfDeath] = useState("");
  const [collectionStart, setCollectionStart] = useState("");
  const [overrideRate, setOverrideRate] = useState("");
  // 'Any form has to be updated to make it greater' — already
  // accepted by the backend, never actually asked for here.
  const [deceasedDateOfBirth, setDeceasedDateOfBirth] = useState("");
  const [burialDate, setBurialDate] = useState("");
  const [funeralDate, setFuneralDate] = useState("");
  const [collectionEnd, setCollectionEnd] = useState("");
  const [showMoreDetails, setShowMoreDetails] = useState(false);

  const family = families?.find((f) => f.id === familyId);
  const hasStandingRate = Boolean(family?.standing_family_rate);

  // 'When someone dies... their membership account should go
  // inactive.' Scoped to the chosen family's own members, since the
  // deceased is overwhelmingly a member of the family whose ledger is
  // being opened — this is a convenience for the common case, not a
  // requirement; the deceased's name is still free text either way.
  const { data: familyMembers } = useQuery({
    queryKey: ["create-funeral-family-members", familyId],
    queryFn: () => membersApi.list({ family: familyId, status: "active" }),
    enabled: Boolean(familyId),
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!deceasedName || !familyId || !causeOfDeath || !dateOfDeath || !collectionStart) return;
    mutate(
      {
        deceased_name: deceasedName,
        deceased_gender: gender,
        deceased_family_id: familyId,
        cause_of_death: causeOfDeath,
        ...(deceasedMemberId ? { deceased_member_id: deceasedMemberId } : {}),
        date_of_death: dateOfDeath,
        collection_start_date: collectionStart,
        own_family_amount: !hasStandingRate ? overrideRate || undefined : undefined,
        ...(deceasedDateOfBirth ? { deceased_date_of_birth: deceasedDateOfBirth } : {}),
        ...(burialDate ? { burial_date: burialDate } : {}),
        ...(funeralDate ? { funeral_date: funeralDate } : {}),
        ...(collectionEnd ? { collection_end_date: collectionEnd } : {}),
      },
      { onSuccess: onClose }
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="font-body flex max-h-[85vh] w-full max-w-lg flex-col overflow-hidden rounded-lg bg-[var(--bg)] text-[var(--ink)] shadow-xl">
        <div className="shrink-0 border-b border-[var(--rule)] p-6 pb-4">
          <div className="flex items-start justify-between gap-4">
            <h2 className="font-display text-xl">Record a funeral</h2>
            <button onClick={onClose} className="shrink-0 text-[var(--ink-soft)] hover:text-[var(--ink)]" aria-label="Close">
              ✕
            </button>
          </div>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">
            Every active member is added to this funeral&apos;s ledger automatically the
            moment you save it — nobody needs to be registered by hand.
          </p>
        </div>
        <div className="overflow-y-auto p-6 pt-4">

        <form onSubmit={submit} className="space-y-5">
          <FormSection label="The deceased">
            <Field
              label="Already a registered member? (optional)"
              wide
              hint={familyId ? "Selecting one automatically moves their own membership to Deceased once this funeral goes live." : "Pick a family below first to search its members."}
            >
              <select
                value={deceasedMemberId}
                onChange={(e) => {
                  setDeceasedMemberId(e.target.value);
                  const picked = familyMembers?.find((m) => m.id === e.target.value);
                  if (picked) { setDeceasedName(picked.full_name); setGender(picked.gender); }
                }}
                disabled={!familyId}
                className={`${FIELD_INPUT_CLASS} disabled:opacity-50`}
              >
                <option value="">Not a registered member / enter name manually</option>
                {familyMembers?.map((m) => (
                  <option key={m.id} value={m.id}>{m.full_name}</option>
                ))}
              </select>
            </Field>
            <Field label="Deceased's name" wide>
              <input
                value={deceasedName}
                onChange={(e) => setDeceasedName(e.target.value)}
                className={FIELD_INPUT_CLASS}
              />
            </Field>
            <Field label="Gender">
              <select
                value={gender}
                onChange={(e) => setGender(e.target.value as "male" | "female")}
                className={FIELD_INPUT_CLASS}
              >
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </Field>
            <Field label="Date of death">
              <input
                type="date"
                value={dateOfDeath}
                onChange={(e) => setDateOfDeath(e.target.value)}
                className={FIELD_INPUT_CLASS}
              />
            </Field>
            <Field label="Cause of death" wide>
              <input
                value={causeOfDeath}
                onChange={(e) => setCauseOfDeath(e.target.value)}
                placeholder="e.g. Natural causes, illness, accident"
                className={FIELD_INPUT_CLASS}
              />
            </Field>
          </FormSection>

          <FormSection label="Family & rate">
            <Field label="Family" wide>
              <select
                value={familyId}
                onChange={(e) => setFamilyId(e.target.value)}
                className={FIELD_INPUT_CLASS}
              >
                <option value="">Choose the deceased&apos;s family…</option>
                {families?.filter((f) => f.status === "active").map((f) => (
                  <option key={f.id} value={f.id}>{f.name}</option>
                ))}
              </select>
            </Field>
            {familyId && (
              <div className="col-span-2 rounded-lg bg-white p-3 text-sm">
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
                      className={`mt-1 ${FIELD_INPUT_CLASS}`}
                    />
                  </div>
                )}
              </div>
            )}
          </FormSection>

          <FormSection label="Collection window">
            <Field label="Contribution collection starts" wide>
              <input
                type="date"
                value={collectionStart}
                onChange={(e) => setCollectionStart(e.target.value)}
                className={FIELD_INPUT_CLASS}
              />
            </Field>
          </FormSection>

          <button
            type="button"
            onClick={() => setShowMoreDetails((v) => !v)}
            className="text-left text-xs font-medium text-[var(--forest)] hover:underline"
          >
            {showMoreDetails ? "Hide additional details" : "+ Add date of birth, burial date, funeral date, collection end date (optional)"}
          </button>
          {showMoreDetails && (
            <FormSection label="More details">
              <Field label="Deceased's date of birth">
                <input
                  type="date" value={deceasedDateOfBirth} onChange={(e) => setDeceasedDateOfBirth(e.target.value)}
                  className={FIELD_INPUT_CLASS}
                />
              </Field>
              <Field label="Collections end">
                <input
                  type="date" value={collectionEnd} onChange={(e) => setCollectionEnd(e.target.value)}
                  className={FIELD_INPUT_CLASS}
                />
              </Field>
              <Field label="Burial date" hint="Used for Asupedeɛ's own burial-morning collection window, if activated">
                <input
                  type="date" value={burialDate} onChange={(e) => setBurialDate(e.target.value)}
                  className={FIELD_INPUT_CLASS}
                />
              </Field>
              <Field label="Funeral date">
                <input
                  type="date" value={funeralDate} onChange={(e) => setFuneralDate(e.target.value)}
                  className={FIELD_INPUT_CLASS}
                />
              </Field>
            </FormSection>
          )}

          {error && <p className="text-sm text-[var(--clay-red)]">{error.message}</p>}

          <div className="flex justify-end gap-2 border-t border-[var(--rule)] pt-4">
            <button type="button" onClick={onClose} className="px-3 py-2 text-sm text-[var(--ink-soft)]">
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="rounded-lg bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {isPending ? "Creating…" : "Create funeral & open ledger"}
            </button>
          </div>
        </form>
        </div>
      </div>
    </div>
  );
}
