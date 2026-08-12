"use client";

import { useState } from "react";
import { useFamilyActions } from "@/lib/hooks/useFamilies";
import { useFamilyUiStore } from "@/store/familyUiStore";
import { DialogShell } from "./DialogShell";

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
      <form onSubmit={submit} className="max-h-[70vh] space-y-4 overflow-y-auto pr-1">
        <div>
          <label className="text-sm font-medium">Family name</label>
          <input
            autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Asona"
            className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
          />
        </div>
        <div>
          <label className="text-sm font-medium">Notes (optional)</label>
          <textarea
            value={description} onChange={(e) => setDescription(e.target.value)} rows={2}
            className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
          />
        </div>

        <div className="rounded-sm bg-[var(--surface)] p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Family Head (Abusuapanin) — required</p>

          <div className="mt-2 grid grid-cols-2 gap-2">
            <input
              value={headFullName} onChange={(e) => setHeadFullName(e.target.value)} placeholder="Full name"
              className="col-span-2 rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
            <select
              value={headGender} onChange={(e) => setHeadGender(e.target.value as "male" | "female")}
              className="rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm"
            >
              <option value="male">Male</option>
              <option value="female">Female</option>
            </select>
            <input
              value={headPhone} onChange={(e) => setHeadPhone(e.target.value)} placeholder="Phone (optional)"
              className="rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
          </div>

          <p className="mt-3 text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Their login</p>
          <div className="mt-2 grid grid-cols-2 gap-2">
            <input
              value={headUsername} onChange={(e) => setHeadUsername(e.target.value)} placeholder="Username"
              className="rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
            <input
              type="password" value={headPassword} onChange={(e) => setHeadPassword(e.target.value)} placeholder="Password (8+ chars)"
              className="rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
          </div>

          <button type="button" onClick={() => setShowMore((v) => !v)} className="mt-3 text-xs text-[var(--forest)] hover:underline">
            {showMore ? "Hide additional details" : "+ Add email, Ghana Card, address, occupation (optional)"}
          </button>
          {showMore && (
            <div className="mt-2 grid grid-cols-2 gap-2">
              <input value={headEmail} onChange={(e) => setHeadEmail(e.target.value)} placeholder="Email" className="rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm" />
              <input value={headGhanaCard} onChange={(e) => setHeadGhanaCard(e.target.value)} placeholder="Ghana Card number" className="rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm" />
              <input value={headAddress} onChange={(e) => setHeadAddress(e.target.value)} placeholder="Residential address" className="col-span-2 rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm" />
              <input value={headOccupation} onChange={(e) => setHeadOccupation(e.target.value)} placeholder="Occupation" className="col-span-2 rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm" />
            </div>
          )}
        </div>

        {registerWithHead.isError && (
          <p className="text-sm text-[var(--clay-red)]">
            {registerWithHead.error instanceof Error ? registerWithHead.error.message : "Couldn't register this family."}
          </p>
        )}
        <div className="flex justify-end gap-2 pt-2">
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
