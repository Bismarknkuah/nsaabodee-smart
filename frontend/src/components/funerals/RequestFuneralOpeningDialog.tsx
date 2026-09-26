"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRequestFuneralOpening } from "@/lib/hooks/useFunerals";
import { membersApi } from "@/lib/api/members";
import { useAuthStore } from "@/store/authStore";
import { Field, FormSection, FIELD_INPUT_CLASS } from "@/components/forms/FormPrimitives";

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
  const [causeOfDeath, setCauseOfDeath] = useState("");
  const [deceasedMemberId, setDeceasedMemberId] = useState("");
  const [dateOfDeath, setDateOfDeath] = useState("");
  const [collectionStartDate, setCollectionStartDate] = useState("");
  // 'Any form has to be updated to make it greater' — these were
  // already accepted by the backend (deceased_date_of_birth,
  // burial_date, funeral_date, collection_end_date all exist on
  // request_funeral_event) but never actually asked for here. Kept
  // optional, in a collapsible "more details" section, matching the
  // registration form's own established pattern — never a blocker
  // for a Family Head who just needs to open the ledger quickly.
  const [deceasedDateOfBirth, setDeceasedDateOfBirth] = useState("");
  const [burialDate, setBurialDate] = useState("");
  const [funeralDate, setFuneralDate] = useState("");
  const [collectionEndDate, setCollectionEndDate] = useState("");
  const [showMoreDetails, setShowMoreDetails] = useState(false);
  // 'The ledger opening has to ask for that person to be nominated.'
  const [nominateRep, setNominateRep] = useState(false);
  const [repUsername, setRepUsername] = useState("");
  const [repPassword, setRepPassword] = useState("");

  // 'When someone dies... their membership account should go
  // inactive.' No explicit family filter needed — a Family Head's own
  // member search is already scoped server-side to their own family.
  const { data: familyMembers } = useQuery({
    queryKey: ["request-opening-family-members"],
    queryFn: () => membersApi.list({ status: "active" }),
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    mutate(
      {
        deceased_name: deceasedName,
        deceased_gender: deceasedGender,
        cause_of_death: causeOfDeath,
        ...(deceasedMemberId ? { deceased_member_id: deceasedMemberId } : {}),
        date_of_death: dateOfDeath,
        collection_start_date: collectionStartDate,
        ...(deceasedDateOfBirth ? { deceased_date_of_birth: deceasedDateOfBirth } : {}),
        ...(burialDate ? { burial_date: burialDate } : {}),
        ...(funeralDate ? { funeral_date: funeralDate } : {}),
        ...(collectionEndDate ? { collection_end_date: collectionEndDate } : {}),
        ...(nominateRep && repUsername && repPassword
          ? { rep_new_username: repUsername, rep_new_password: repPassword }
          : {}),
      },
      { onSuccess: onClose }
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="font-body flex max-h-[85vh] w-full max-w-md flex-col overflow-hidden rounded-lg bg-[var(--bg)] text-[var(--ink)] shadow-xl">
        <div className="shrink-0 border-b border-[var(--rule)] p-6 pb-4">
          <div className="flex items-start justify-between gap-4">
            <h2 className="font-display text-xl">Request a funeral opening</h2>
            <button onClick={onClose} className="shrink-0 text-[var(--ink-soft)] hover:text-[var(--ink)]" aria-label="Close">✕</button>
          </div>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">
            This opens for <strong>{user?.community_name ?? "your community"}</strong>&apos;s own
            family — nobody is billed a single cedi until two of the Secretary, Chairman, or
            Community Admin approve it.
          </p>
        </div>
        <div className="overflow-y-auto p-6 pt-4">
        <form onSubmit={submit} className="space-y-5">
          <FormSection label="The deceased">
            <Field label="Already a registered member? (optional)" wide hint="Selecting one automatically moves their own membership to Deceased once this funeral is approved.">
              <select
                value={deceasedMemberId}
                onChange={(e) => {
                  setDeceasedMemberId(e.target.value);
                  const picked = familyMembers?.find((m) => m.id === e.target.value);
                  if (picked) { setDeceasedName(picked.full_name); setDeceasedGender(picked.gender); }
                }}
                className={FIELD_INPUT_CLASS}
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
                value={deceasedGender}
                onChange={(e) => setDeceasedGender(e.target.value as "male" | "female")}
                className={FIELD_INPUT_CLASS}
              >
                <option value="male">Male</option>
                <option value="female">Female</option>
              </select>
            </Field>
            <Field label="Date of death">
              <input
                type="date" value={dateOfDeath} onChange={(e) => setDateOfDeath(e.target.value)}
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

          <FormSection label="Collection window">
            <Field label="Collections start" wide>
              <input
                type="date" value={collectionStartDate} onChange={(e) => setCollectionStartDate(e.target.value)}
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
                  type="date" value={collectionEndDate} onChange={(e) => setCollectionEndDate(e.target.value)}
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

          <div className="border-t border-[var(--rule)] pt-4">
            <label className="flex items-center gap-2 text-sm font-medium">
              <input type="checkbox" checked={nominateRep} onChange={(e) => setNominateRep(e.target.checked)} />
              Nominate a Deceased Rep now
            </label>
            <p className="mt-1 text-xs text-[var(--ink-soft)]">
              Represents your family on the funeral committee. Optional — this can also be done later
              from the Families page. Starts pending either way, needing a Secretary, Chairman, or
              Community Admin to approve.
            </p>
            {nominateRep && (
              <div className="mt-3 grid grid-cols-2 gap-3">
                <div>
                  <label className="text-sm font-medium">Rep&apos;s username</label>
                  <input
                    value={repUsername}
                    onChange={(e) => setRepUsername(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium">Temporary password</label>
                  <input
                    type="password"
                    value={repPassword}
                    onChange={(e) => setRepPassword(e.target.value)}
                    className="mt-1 w-full rounded-lg border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
                  />
                </div>
              </div>
            )}
          </div>

          {error && <p className="text-sm text-[var(--clay-red)]">{error.message}</p>}

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-3 py-2 text-sm text-[var(--ink-soft)]">Cancel</button>
            <button
              type="submit"
              disabled={isPending || !deceasedName || !dateOfDeath || !collectionStartDate}
              className="rounded-lg bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {isPending ? "Sending request…" : "Send for approval"}
            </button>
          </div>
        </form>
        </div>
      </div>
    </div>
  );
}
