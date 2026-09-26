"use client";

import { useEffect, useState } from "react";
import { useFamilies } from "@/lib/hooks/useFamilies";
import { useMemberActions } from "@/lib/hooks/useMembers";
import { useAuthStore } from "@/store/authStore";
import { Field, FormSection, FIELD_INPUT_CLASS } from "@/components/forms/FormPrimitives";

const COMMUNITY_WIDE_ROLES = ["community_admin", "chairman", "secretary"];
// 'When the family head is adding a new member, the other family
// option shouldn't be available for him to select, the family should
// automatically be selected as he's a leader of a specific family.'
// Family Secretary can also register members (the backend's own
// family-scoping already restricts them to their own family too — see
// the family data isolation audit), so the same restriction applies
// to both, not just the Head.
const FAMILY_SCOPED_ROLES = ["family_head", "family_secretary"];

export function RegisterMemberDialog({ onClose }: { onClose: () => void }) {
  const { data: families } = useFamilies(false);
  const { register } = useMemberActions();
  const user = useAuthStore((s) => s.user);
  const canSetTownLeader = Boolean(user?.is_superuser || (user?.role && COMMUNITY_WIDE_ROLES.includes(user.role)));
  const isFamilyScoped = Boolean(user?.role && FAMILY_SCOPED_ROLES.includes(user.role));
  const ownFamily = isFamilyScoped
    ? families?.find((f) => f.family_head?.id === user?.linked_member_id || f.family_secretary?.id === user?.linked_member_id)
    : undefined;

  const [fullName, setFullName] = useState("");
  const [gender, setGender] = useState<"male" | "female">("male");
  const [familyId, setFamilyId] = useState("");
  const [phone, setPhone] = useState("");
  const [ghanaCard, setGhanaCard] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  // 'When registering a member or adding a member, the system should
  // required more information.' All of these already existed on the
  // backend model and were already accepted by the API — the real gap
  // was this form never actually collecting them. Date of birth also
  // enables the birthday message feature (see notifications.tasks).
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [email, setEmail] = useState("");
  const [address, setAddress] = useState("");
  const [occupation, setOccupation] = useState("");
  const [emergencyContactName, setEmergencyContactName] = useState("");
  const [emergencyContactPhone, setEmergencyContactPhone] = useState("");
  // 'Ask more information about the person, mother, father,
  // background.' Same optional, "more details" treatment as the
  // fields above — a fuller record for a family or community that
  // wants it, never a blocker for a quick registration that doesn't.
  const [motherName, setMotherName] = useState("");
  const [fatherName, setFatherName] = useState("");
  const [hometown, setHometown] = useState("");
  const [maritalStatus, setMaritalStatus] = useState<"" | "single" | "married" | "divorced" | "widowed">("");
  const [spouseName, setSpouseName] = useState("");
  const [showMoreDetails, setShowMoreDetails] = useState(false);
  const [familySeniority, setFamilySeniority] = useState<"senior" | "junior">("junior");
  const [isTownLeader, setIsTownLeader] = useState(false);
  const [duplicates, setDuplicates] = useState<{ full_name: string; membership_number: string }[] | null>(null);
  const [blockedDuplicateMessage, setBlockedDuplicateMessage] = useState<string | null>(null);

  useEffect(() => {
    if (ownFamily) setFamilyId(ownFamily.id);
  }, [ownFamily]);

  const buildForm = (forceDespiteDuplicate = false) => {
    const form = new FormData();
    form.set("full_name", fullName.trim());
    form.set("gender", gender);
    if (familyId) form.set("family_id", familyId);
    if (phone) form.set("phone", phone);
    if (ghanaCard) form.set("ghana_card_number", ghanaCard);
    if (photo) form.set("photo", photo);
    if (dateOfBirth) form.set("date_of_birth", dateOfBirth);
    if (email) form.set("email", email);
    if (address) form.set("address", address);
    if (occupation) form.set("occupation", occupation);
    if (emergencyContactName) form.set("emergency_contact_name", emergencyContactName);
    if (emergencyContactPhone) form.set("emergency_contact_phone", emergencyContactPhone);
    if (motherName) form.set("mother_name", motherName);
    if (fatherName) form.set("father_name", fatherName);
    if (hometown) form.set("hometown", hometown);
    if (maritalStatus) form.set("marital_status", maritalStatus);
    if (spouseName) form.set("spouse_name", spouseName);
    if (gender === "male") form.set("family_seniority", familySeniority);
    if (canSetTownLeader && isTownLeader) form.set("is_town_leader", "true");
    if (forceDespiteDuplicate) form.set("force_despite_duplicate", "true");
    return form;
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!fullName.trim()) return;
    setBlockedDuplicateMessage(null);
    register.mutate(buildForm(), {
      onSuccess: (member) => {
        if (member.possible_duplicates?.length) {
          setDuplicates(member.possible_duplicates);
        } else {
          onClose();
        }
      },
      onError: (err) => {
        // "One person should not be added twice" — an exact name+phone
        // match is blocked outright by the backend, not just flagged.
        // The message names the existing member, so surface it directly
        // rather than a generic error, and offer the explicit override.
        if (err.message.toLowerCase().includes("already registered with this phone number")) {
          setBlockedDuplicateMessage(err.message);
        }
      },
    });
  };

  const registerAnyway = () => {
    register.mutate(buildForm(true), {
      onSuccess: (member) => {
        setBlockedDuplicateMessage(null);
        if (member.possible_duplicates?.length) {
          setDuplicates(member.possible_duplicates);
        } else {
          onClose();
        }
      },
    });
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="font-body flex max-h-[85vh] w-full max-w-lg flex-col overflow-hidden rounded-lg bg-[var(--bg)] text-[var(--ink)] shadow-xl">
        <div className="shrink-0 border-b border-[var(--rule)] p-6 pb-4">
          <div className="flex items-start justify-between gap-4">
            <h2 className="font-display text-xl">Register a member</h2>
            <button onClick={onClose} className="shrink-0 text-[var(--ink-soft)] hover:text-[var(--ink)]" aria-label="Close">
              ✕
            </button>
          </div>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">
            A membership number and QR-coded digital card are generated automatically. This
            works offline in the mobile app too — it syncs the moment a connection returns.
          </p>
        </div>
        <div className="overflow-y-auto p-6 pt-4">

        {duplicates && duplicates.length > 0 ? (
          <div className="mt-4 space-y-3">
            <div className="rounded-lg bg-[var(--gold-soft)] p-3 text-sm text-[var(--gold)]">
              This member was registered, but {duplicates.length} existing member
              {duplicates.length === 1 ? " looks" : "s look"} similar — worth a quick check
              in case this is a duplicate:
            </div>
            <ul className="space-y-1 text-sm">
              {duplicates.map((d) => (
                <li key={d.membership_number} className="rounded-lg bg-white px-3 py-2">
                  {d.full_name} <span className="font-mono text-xs text-[var(--ink-soft)]">({d.membership_number})</span>
                </li>
              ))}
            </ul>
            <div className="flex justify-end">
              <button onClick={onClose} className="rounded-lg bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white">
                Done
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-4 space-y-5">
            <FormSection label="Who they are">
              <Field label="Full name" wide>
                <input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
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
              <Field label="Family" hint={isFamilyScoped ? "You can only register members into your own family." : undefined}>
                {isFamilyScoped ? (
                  <select
                    value={familyId}
                    disabled
                    className="w-full cursor-not-allowed rounded-lg border border-[var(--rule)] bg-[var(--bg)] px-3 py-2 text-sm text-[var(--ink-soft)]"
                  >
                    <option value={ownFamily?.id ?? ""}>{ownFamily?.name ?? "Your family"}</option>
                  </select>
                ) : (
                  <select
                    value={familyId}
                    onChange={(e) => setFamilyId(e.target.value)}
                    className={FIELD_INPUT_CLASS}
                  >
                    <option value="">Choose family…</option>
                    {families?.filter((f) => f.status === "active").map((f) => (
                      <option key={f.id} value={f.id}>{f.name}</option>
                    ))}
                  </select>
                )}
              </Field>
            </FormSection>

            <FormSection label="Reaching them">
              <Field label="Phone">
                <input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className={FIELD_INPUT_CLASS}
                />
              </Field>
              <Field label="Ghana Card (optional)">
                <input
                  value={ghanaCard}
                  onChange={(e) => setGhanaCard(e.target.value)}
                  className={FIELD_INPUT_CLASS}
                />
              </Field>
            </FormSection>

            <button
              type="button"
              onClick={() => setShowMoreDetails((v) => !v)}
              className="text-xs text-[var(--forest)] hover:underline"
            >
              {showMoreDetails ? "Hide additional details" : "+ Add date of birth, email, address, occupation, parents, hometown, emergency contact (optional)"}
            </button>
            {showMoreDetails && (
              <>
                <FormSection label="Personal details">
                  <Field label="Date of birth" hint="Lets us wish them well on their birthday">
                    <input
                      type="date" value={dateOfBirth} onChange={(e) => setDateOfBirth(e.target.value)}
                      className={FIELD_INPUT_CLASS}
                    />
                  </Field>
                  <Field label="Email">
                    <input
                      type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                      className={FIELD_INPUT_CLASS}
                    />
                  </Field>
                  <Field label="Residential address" wide>
                    <input
                      value={address} onChange={(e) => setAddress(e.target.value)}
                      className={FIELD_INPUT_CLASS}
                    />
                  </Field>
                  <Field label="Occupation" wide>
                    <input
                      value={occupation} onChange={(e) => setOccupation(e.target.value)}
                      className={FIELD_INPUT_CLASS}
                    />
                  </Field>
                </FormSection>

                <FormSection label="Family background">
                  <Field label="Mother's name">
                    <input
                      value={motherName} onChange={(e) => setMotherName(e.target.value)}
                      className={FIELD_INPUT_CLASS}
                    />
                  </Field>
                  <Field label="Father's name">
                    <input
                      value={fatherName} onChange={(e) => setFatherName(e.target.value)}
                      className={FIELD_INPUT_CLASS}
                    />
                  </Field>
                  <Field label="Hometown" hint="Their family's own ancestral origin, not their current address">
                    <input
                      value={hometown} onChange={(e) => setHometown(e.target.value)}
                      className={FIELD_INPUT_CLASS}
                    />
                  </Field>
                  <Field label="Marital status">
                    <select
                      value={maritalStatus}
                      onChange={(e) => setMaritalStatus(e.target.value as typeof maritalStatus)}
                      className={FIELD_INPUT_CLASS}
                    >
                      <option value="">Not specified</option>
                      <option value="single">Single</option>
                      <option value="married">Married</option>
                      <option value="divorced">Divorced</option>
                      <option value="widowed">Widowed</option>
                    </select>
                  </Field>
                  {maritalStatus === "married" && (
                    <Field label="Spouse's name" wide>
                      <input
                        value={spouseName} onChange={(e) => setSpouseName(e.target.value)}
                        className={FIELD_INPUT_CLASS}
                      />
                    </Field>
                  )}
                </FormSection>

                <FormSection label="In case of emergency">
                  <Field label="Emergency contact name">
                    <input
                      value={emergencyContactName} onChange={(e) => setEmergencyContactName(e.target.value)}
                      className={FIELD_INPUT_CLASS}
                    />
                  </Field>
                  <Field label="Emergency contact phone">
                    <input
                      value={emergencyContactPhone} onChange={(e) => setEmergencyContactPhone(e.target.value)}
                      className={FIELD_INPUT_CLASS}
                    />
                  </Field>
                </FormSection>
              </>
            )}

            {(gender === "male" || canSetTownLeader) && (
              <FormSection label="Funeral contribution">
                {gender === "male" && (
                  <Field
                    label="If their own family holds a funeral"
                    wide
                    hint="Which family contribution tier he pays — ignored entirely if he later becomes the family head, which always pays the head rate instead."
                  >
                    <select
                      value={familySeniority}
                      onChange={(e) => setFamilySeniority(e.target.value as "senior" | "junior")}
                      className={FIELD_INPUT_CLASS}
                    >
                      <option value="junior">Nephew tier (junior)</option>
                      <option value="senior">Uncle tier (senior)</option>
                    </select>
                  </Field>
                )}
                {canSetTownLeader && (
                  <label className="col-span-2 flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={isTownLeader} onChange={(e) => setIsTownLeader(e.target.checked)} />
                    Town leader (chief or elder) — pays the community&apos;s flat town-leader rate on every funeral
                  </label>
                )}
              </FormSection>
            )}

            <div>
              <label className="text-sm font-medium">Photo (optional)</label>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => setPhoto(e.target.files?.[0] ?? null)}
                className="mt-1 w-full text-sm"
              />
            </div>

            {blockedDuplicateMessage && (
              <div className="rounded-lg bg-[var(--clay-red-soft)] p-3 text-sm text-[var(--clay-red)]">
                <p>{blockedDuplicateMessage}</p>
                <button
                  type="button"
                  onClick={registerAnyway}
                  className="mt-2 rounded-lg border border-[var(--clay-red)] px-3 py-1 text-xs font-medium hover:bg-white"
                >
                  This is genuinely a different person — register anyway
                </button>
              </div>
            )}
            {register.isError && !blockedDuplicateMessage && (
              <p className="text-sm text-[var(--clay-red)]">{register.error.message}</p>
            )}

            <div className="flex justify-end gap-2 border-t border-[var(--rule)] pt-4">
              <button type="button" onClick={onClose} className="px-3 py-2 text-sm text-[var(--ink-soft)]">
                Cancel
              </button>
              <button
                type="submit"
                disabled={register.isPending}
                className="rounded-lg bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
              >
                {register.isPending ? "Registering…" : "Register member"}
              </button>
            </div>
          </form>
        )}
        </div>
      </div>
    </div>
  );
}
