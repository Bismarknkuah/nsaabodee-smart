"use client";

import { useState } from "react";
import { useFamilyActions } from "@/lib/hooks/useFamilies";
import { useFamilyUiStore } from "@/store/familyUiStore";
import { DialogShell } from "./DialogShell";
import { Field, FormSection, FIELD_INPUT_CLASS } from "@/components/forms/FormPrimitives";

/**
 * "When a new family is created, the system must require the
 * registration of the Family Head as part of the process... created
 * automatically and linked to the newly created family." Only name,
 * gender, and login credentials are truly required beyond the family's
 * own name — everything else on the Head's profile is optional, the
 * same way registering an ordinary member already works elsewhere.
 */
export function AddFamilyDialog() {
  const closeDialog = useFamilyUiStore((s) => s.closeDialog);
  const { registerWithHead } = useFamilyActions();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [headFullName, setHeadFullName] = useState("");
  const [headGender, setHeadGender] = useState<"male" | "female">("male");
  const [headUsername, setHeadUsername] = useState("");
  const [headPassword, setHeadPassword] = useState("");
  const [showMore, setShowMore] = useState(false);
  const [headPhone, setHeadPhone] = useState("");
  const [headEmail, setHeadEmail] = useState("");
  const [headGhanaCard, setHeadGhanaCard] = useState("");
  const [headAddress, setHeadAddress] = useState("");
  const [headOccupation, setHeadOccupation] = useState("");

  const canSubmit = name.trim() && headFullName.trim() && headUsername.trim() && headPassword.length >= 8;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    registerWithHead.mutate(
      {
        name: name.trim(), description: description.trim() || undefined,
        head_full_name: headFullName.trim(), head_gender: headGender,
        head_username: headUsername.trim(), head_password: headPassword,
        head_phone: headPhone.trim() || undefined, head_email: headEmail.trim() || undefined,
        head_ghana_card_number: headGhanaCard.trim() || undefined,
        head_address: headAddress.trim() || undefined, head_occupation: headOccupation.trim() || undefined,
      },
      { onSuccess: closeDialog }
    );
  };

  return (
    <DialogShell
      title="Register a new family"
      description="Every new family needs its own Family Head registered from the start — their login is created together with the family, right here."
    >
      <form onSubmit={submit} className="space-y-5">
        <FormSection label="Family">
          <Field label="Family name" wide>
            <input
              autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Asona"
              className={FIELD_INPUT_CLASS}
            />
          </Field>
          <Field label="Notes (optional)" wide>
            <textarea
              value={description} onChange={(e) => setDescription(e.target.value)} rows={2}
              className={FIELD_INPUT_CLASS}
            />
          </Field>
        </FormSection>

        <FormSection label="Family Head (Abusuapanin) — required">
          <Field label="Full name" wide>
            <input
              value={headFullName} onChange={(e) => setHeadFullName(e.target.value)}
              className={FIELD_INPUT_CLASS}
            />
          </Field>
          <Field label="Gender">
            <select
              value={headGender} onChange={(e) => setHeadGender(e.target.value as "male" | "female")}
              className={FIELD_INPUT_CLASS}
            >
              <option value="male">Male</option>
              <option value="female">Female</option>
            </select>
          </Field>
          <Field label="Phone (optional)">
            <input
              value={headPhone} onChange={(e) => setHeadPhone(e.target.value)}
              className={FIELD_INPUT_CLASS}
            />
          </Field>
        </FormSection>

        <FormSection label="Their login">
          <Field label="Username">
            <input
              value={headUsername} onChange={(e) => setHeadUsername(e.target.value)}
              className={FIELD_INPUT_CLASS}
            />
          </Field>
          <Field label="Password (8+ chars)">
            <input
              type="password" value={headPassword} onChange={(e) => setHeadPassword(e.target.value)}
              className={FIELD_INPUT_CLASS}
            />
          </Field>
        </FormSection>

        <button type="button" onClick={() => setShowMore((v) => !v)} className="text-xs text-[var(--forest)] hover:underline">
          {showMore ? "Hide additional details" : "+ Add email, Ghana Card, address, occupation (optional)"}
        </button>
        {showMore && (
          <FormSection label="More about the Family Head">
            <Field label="Email">
              <input value={headEmail} onChange={(e) => setHeadEmail(e.target.value)} className={FIELD_INPUT_CLASS} />
            </Field>
            <Field label="Ghana Card number">
              <input value={headGhanaCard} onChange={(e) => setHeadGhanaCard(e.target.value)} className={FIELD_INPUT_CLASS} />
            </Field>
            <Field label="Residential address" wide>
              <input value={headAddress} onChange={(e) => setHeadAddress(e.target.value)} className={FIELD_INPUT_CLASS} />
            </Field>
            <Field label="Occupation" wide>
              <input value={headOccupation} onChange={(e) => setHeadOccupation(e.target.value)} className={FIELD_INPUT_CLASS} />
            </Field>
          </FormSection>
        )}

        {registerWithHead.isError && (
          <p className="text-sm text-[var(--clay-red)]">
            {registerWithHead.error instanceof Error ? registerWithHead.error.message : "Couldn't register this family."}
          </p>
        )}
        <div className="flex justify-end gap-2 border-t border-[var(--rule)] pt-4">
          <button type="button" onClick={closeDialog} className="px-3 py-2 text-sm text-[var(--ink-soft)]">
            Cancel
          </button>
          <button
            type="submit"
            disabled={registerWithHead.isPending || !canSubmit}
            className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {registerWithHead.isPending ? "Registering…" : "Register family"}
          </button>
        </div>
      </form>
    </DialogShell>
  );
}
