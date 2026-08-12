"use client";

import "@/styles/family-registry-tokens.css";
import { useRef, useState } from "react";
import { accountsApi } from "@/lib/api/accounts";
import { useAuthStore } from "@/store/authStore";

/**
 * "Should be able to change their profile and upload dp." Deliberately
 * self-service only for email and photo — role, community, and
 * username stay administrative decisions made by whoever manages that
 * account, not something the account holder changes for themselves.
 */
export default function ProfilePage() {
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [email, setEmail] = useState(user?.email ?? "");
  const [phoneNumber, setPhoneNumber] = useState(user?.phone_number ?? "");
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileSaved, setProfileSaved] = useState(false);

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [savingPassword, setSavingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSaved, setPasswordSaved] = useState(false);

  if (!user) return null;

  const onPickPhoto = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setSelectedFile(file);
    setPhotoPreview(URL.createObjectURL(file));
  };

  const saveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingProfile(true);
    setProfileError(null);
    setProfileSaved(false);
    try {
      const updated = await accountsApi.updateProfile({
        email,
        phone_number: phoneNumber,
        profile_photo: selectedFile ?? undefined,
      });
      setUser(updated);
      setSelectedFile(null);
      setProfileSaved(true);
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Could not save your profile.");
    } finally {
      setSavingProfile(false);
    }
  };

  const savePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingPassword(true);
    setPasswordError(null);
    setPasswordSaved(false);
    try {
      await accountsApi.changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setPasswordSaved(true);
    } catch (err) {
      setPasswordError(err instanceof Error ? err.message : "Could not change your password.");
    } finally {
      setSavingPassword(false);
    }
  };

  const displayPhoto = photoPreview ?? user.profile_photo_url;

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Account</p>
        <h1 className="font-display mt-1 text-4xl">My Profile</h1>
      </header>

      <main className="mx-auto max-w-2xl px-8 py-8">
        {/* ---------- Profile card ---------- */}
        <section className="rounded-sm border border-[var(--rule)] bg-white p-6">
          <h2 className="font-display text-xl">Profile</h2>

          <form onSubmit={saveProfile} className="mt-4 space-y-4">
            <div className="flex items-center gap-5">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="group relative h-20 w-20 shrink-0 overflow-hidden rounded-full border border-[var(--rule)] bg-[var(--surface)]"
                title="Change photo"
              >
                {displayPhoto ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={displayPhoto} alt="" className="h-full w-full object-cover" />
                ) : (
                  <span className="flex h-full w-full items-center justify-center font-display text-2xl text-[var(--ink-soft)]">
                    {user.username.slice(0, 1).toUpperCase()}
                  </span>
                )}
                <span className="absolute inset-0 flex items-center justify-center bg-black/0 text-[10px] font-medium text-transparent transition group-hover:bg-black/50 group-hover:text-white">
                  Change
                </span>
              </button>
              <input ref={fileInputRef} type="file" accept="image/*" onChange={onPickPhoto} className="hidden" />
              <div>
                <p className="font-medium">{user.username}</p>
                <p className="text-xs text-[var(--ink-soft)]">{user.role.replace(/_/g, " ")}</p>
                {user.community_name && <p className="text-xs text-[var(--ink-soft)]">{user.community_name}</p>}
              </div>
            </div>

            <div>
              <label className="text-sm font-medium">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
              />
            </div>

            <div>
              <label className="text-sm font-medium">Phone number</label>
              <input
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                placeholder="+233 XX XXX XXXX"
                className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
              />
              <p className="mt-1 text-xs text-[var(--ink-soft)]">Setting this lets you sign in with a one-time SMS code instead of your password.</p>
            </div>

            {profileError && <p className="text-sm text-[var(--clay-red)]">{profileError}</p>}
            {profileSaved && <p className="text-sm" style={{ color: "var(--forest)" }}>Saved.</p>}

            <button
              type="submit"
              disabled={savingProfile}
              className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {savingProfile ? "Saving…" : "Save changes"}
            </button>
          </form>
        </section>

        {/* ---------- Password card ---------- */}
        <section className="mt-6 rounded-sm border border-[var(--rule)] bg-white p-6">
          <h2 className="font-display text-xl">Change password</h2>
          <form onSubmit={savePassword} className="mt-4 space-y-4">
            <div>
              <label className="text-sm font-medium">Current password</label>
              <input
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                autoComplete="current-password"
                className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
              />
            </div>
            <div>
              <label className="text-sm font-medium">New password</label>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
                minLength={8}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
              />
              <p className="mt-1 text-xs text-[var(--ink-soft)]">At least 8 characters.</p>
            </div>

            {passwordError && <p className="text-sm text-[var(--clay-red)]">{passwordError}</p>}
            {passwordSaved && <p className="text-sm" style={{ color: "var(--forest)" }}>Password changed.</p>}

            <button
              type="submit"
              disabled={savingPassword || !currentPassword || newPassword.length < 8}
              className="rounded-sm border border-[var(--rule)] px-4 py-2 text-sm font-medium hover:border-[var(--forest)] hover:text-[var(--forest)] disabled:opacity-60"
            >
              {savingPassword ? "Changing…" : "Change password"}
            </button>
          </form>
        </section>
      </main>
    </div>
  );
}
