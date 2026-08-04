"use client";

import { useEffect, useState } from "react";
import { useFamilies } from "@/lib/hooks/useFamilies";
import { useMemberActions } from "@/lib/hooks/useMembers";
import { useAuthStore } from "@/store/authStore";

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
      <div className="font-body w-full max-w-lg rounded-sm bg-[var(--surface)] p-6 text-[var(--ink)] shadow-xl">
        <div className="flex items-start justify-between gap-4">
          <h2 className="font-display text-xl">Register a member</h2>
          <button onClick={onClose} className="text-[var(--ink-soft)] hover:text-[var(--ink)]" aria-label="Close">
            ✕
          </button>
        </div>
        <p className="mt-1 text-sm text-[var(--ink-soft)]">
          A membership number and QR-coded digital card are generated automatically. This
          works offline in the mobile app too — it syncs the moment a connection returns.
        </p>

        {duplicates && duplicates.length > 0 ? (
          <div className="mt-4 space-y-3">
            <div className="rounded-sm bg-[var(--gold-soft)] p-3 text-sm text-[var(--gold)]">
              This member was registered, but {duplicates.length} existing member
              {duplicates.length === 1 ? " looks" : "s look"} similar — worth a quick check
              in case this is a duplicate:
            </div>
            <ul className="space-y-1 text-sm">
              {duplicates.map((d) => (
                <li key={d.membership_number} className="rounded-sm bg-white px-3 py-2">
                  {d.full_name} <span className="font-mono text-xs text-[var(--ink-soft)]">({d.membership_number})</span>
                </li>
              ))}
            </ul>
            <div className="flex justify-end">
              <button onClick={onClose} className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white">
                Done
              </button>
            </div>
          </div>
        ) : (
          <form onSubmit={submit} className="mt-4 space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2">
                <label className="text-sm font-medium">Full name</label>
                <input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
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
                <label className="text-sm font-medium">Family</label>
                {isFamilyScoped ? (
                  <>
                    <select
                      value={familyId}
                      disabled
                      className="mt-1 w-full cursor-not-allowed rounded-sm border border-[var(--rule)] bg-[var(--surface)] px-3 py-2 text-sm text-[var(--ink-soft)]"
                    >
                      <option value={ownFamily?.id ?? ""}>{ownFamily?.name ?? "Your family"}</option>
                    </select>
                    <p className="mt-1 text-xs text-[var(--ink-soft)]">
                      You can only register members into your own family.
                    </p>
                  </>
                ) : (
                  <select
                    value={familyId}
                    onChange={(e) => setFamilyId(e.target.value)}
                    className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
                  >
                    <option value="">Choose family…</option>
                    {families?.filter((f) => f.status === "active").map((f) => (
                      <option key={f.id} value={f.id}>{f.name}</option>
                    ))}
                  </select>
                )}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium">Phone</label>
                <input
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
                />
              </div>
              <div>
                <label className="text-sm font-medium">Ghana Card (optional)</label>
                <input
                  value={ghanaCard}
                  onChange={(e) => setGhanaCard(e.target.value)}
                  className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
                />
              </div>
            </div>

            {gender === "male" && (
              <div>
                <label className="text-sm font-medium">If their own family holds a funeral</label>
                <select
                  value={familySeniority}
                  onChange={(e) => setFamilySeniority(e.target.value as "senior" | "junior")}
                  className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
                >
                  <option value="junior">Nephew tier (junior)</option>
                  <option value="senior">Uncle tier (senior)</option>
                </select>
                <p className="mt-1 text-xs text-[var(--ink-soft)]">
                  Which family contribution tier he pays — ignored entirely if he later
                  becomes the family head, which always pays the head rate instead.
                </p>
              </div>
            )}

            {canSetTownLeader && (
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={isTownLeader} onChange={(e) => setIsTownLeader(e.target.checked)} />
                Town leader (chief or elder) — pays the community&apos;s flat town-leader rate on every funeral
              </label>
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
              <div className="rounded-sm bg-[var(--clay-red-soft)] p-3 text-sm text-[var(--clay-red)]">
                <p>{blockedDuplicateMessage}</p>
                <button
                  type="button"
                  onClick={registerAnyway}
                  className="mt-2 rounded-sm border border-[var(--clay-red)] px-3 py-1 text-xs font-medium hover:bg-white"
                >
                  This is genuinely a different person — register anyway
                </button>
              </div>
            )}
            {register.isError && !blockedDuplicateMessage && (
              <p className="text-sm text-[var(--clay-red)]">{register.error.message}</p>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <button type="button" onClick={onClose} className="px-3 py-2 text-sm text-[var(--ink-soft)]">
                Cancel
              </button>
              <button
                type="submit"
                disabled={register.isPending}
                className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
              >
                {register.isPending ? "Registering…" : "Register member"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
