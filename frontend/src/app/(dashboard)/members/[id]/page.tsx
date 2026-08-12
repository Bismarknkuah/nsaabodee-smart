"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useParams } from "next/navigation";
import { useMember, useMemberCard, useMemberActions } from "@/lib/hooks/useMembers";
import { useAuthStore } from "@/store/authStore";

const ASSIGNABLE_ROLES = [
  "community_admin", "traditional_leader", "chairman", "secretary",
  "treasurer", "financial_secretary", "auditor", "collector",
  "family_head", "family_secretary", "family_treasurer",
  "community_member", "guest", "bereaved_rep", "notification_officer",
];

export default function MemberDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: member } = useMember(id);
  const { data: card } = useMemberCard(id);
  const { linkUser, assignRole, revokeRole } = useMemberActions();
  const currentUser = useAuthStore((s) => s.user);
  const isCommunityAdmin = currentUser?.role === "community_admin";
  const [username, setUsername] = useState("");
  const [selectedRole, setSelectedRole] = useState("collector");
  const [newLoginUsername, setNewLoginUsername] = useState("");
  const [newLoginPassword, setNewLoginPassword] = useState("");

  if (!member) return null;

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
          {member.membership_number}
        </p>
        <h1 className="font-display mt-1 text-4xl">{member.full_name}</h1>
        <p className="mt-1 text-sm text-[var(--ink-soft)]">
          {member.family_detail?.name ?? "No family assigned"} · {member.status}
        </p>
      </header>

      <main className="grid gap-6 px-8 py-8 md:grid-cols-2">
        <section>
          <h2 className="font-display text-lg">Details</h2>
          <dl className="mt-3 space-y-2 text-sm">
            <Row label="Gender" value={member.gender} />
            <Row label="Phone" value={member.phone || "—"} />
            <Row label="Address" value={member.address || "—"} />
            <Row label="Occupation" value={member.occupation || "—"} />
            <Row label="Ghana Card" value={member.ghana_card_number || "—"} />
            <Row label="Emergency contact" value={member.emergency_contact_name || "—"} />
            <Row
              label="Contribution standing"
              value={
                member.defaulter_tier === "none"
                  ? "In good standing"
                  : `${member.missed_contributions_count} missed contribution(s) — ${member.defaulter_tier.replace("_", " ")}`
              }
            />
          </dl>
        </section>

        <section className="rounded-sm border border-[var(--rule)] bg-white p-6 md:col-span-2">
          <h2 className="font-display text-lg">App account</h2>
          {member.linked_username ? (
            <p className="mt-2 text-sm text-[var(--ink-soft)]">
              Linked to the login <span className="font-mono font-medium text-[var(--ink)]">{member.linked_username}</span>.
              This member can see their own receipts under &quot;My Receipts&quot; when signed in.
            </p>
          ) : (
            <div className="mt-2">
              <p className="text-sm text-[var(--ink-soft)]">
                Not linked to any login yet — this member can&apos;t see a personal receipts
                dashboard until an account is linked.
              </p>
              <div className="mt-2 flex gap-2">
                <input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Username of their app login"
                  className="w-64 rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
                />
                <button
                  onClick={() => username && linkUser.mutate({ id: member.id, username })}
                  disabled={!username || linkUser.isPending}
                  className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
                >
                  Link account
                </button>
              </div>
              {linkUser.isError && <p className="mt-1 text-sm text-[var(--clay-red)]">{linkUser.error.message}</p>}
            </div>
          )}
        </section>

        {isCommunityAdmin && (
          <section className="rounded-sm border border-[var(--rule)] bg-white p-6 md:col-span-2">
            <h2 className="font-display text-lg">Assign a role</h2>
            <p className="mt-1 text-sm text-[var(--ink-soft)]">
              {member.linked_username
                ? `Change ${member.linked_username}'s role, or leave it as-is.`
                : "This member has no login yet — creating one here also assigns their role."}
            </p>
            <div className="mt-3 flex flex-wrap items-end gap-2">
              <select
                value={selectedRole}
                onChange={(e) => setSelectedRole(e.target.value)}
                className="rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
              >
                {ASSIGNABLE_ROLES.map((r) => (
                  <option key={r} value={r}>{r.replace(/_/g, " ")}</option>
                ))}
              </select>
              {!member.linked_username && (
                <>
                  <input
                    value={newLoginUsername}
                    onChange={(e) => setNewLoginUsername(e.target.value)}
                    placeholder="New username"
                    className="w-48 rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
                  />
                  <input
                    type="password"
                    value={newLoginPassword}
                    onChange={(e) => setNewLoginPassword(e.target.value)}
                    placeholder="New password"
                    className="w-48 rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
                  />
                </>
              )}
              <button
                onClick={() => assignRole.mutate({ id: member.id, role: selectedRole, username: newLoginUsername || undefined, password: newLoginPassword || undefined })}
                disabled={assignRole.isPending || (!member.linked_username && (!newLoginUsername || !newLoginPassword))}
                className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
              >
                {assignRole.isPending ? "Saving…" : "Assign role"}
              </button>
              {member.linked_role && member.linked_role !== "community_member" && (
                <button
                  onClick={() => revokeRole.mutate(member.id)}
                  disabled={revokeRole.isPending}
                  className="rounded-sm border border-[var(--clay-red)] px-4 py-2 text-sm font-medium text-[var(--clay-red)] disabled:opacity-60"
                  title={`Revoke ${member.linked_role} and return to Community Member`}
                >
                  {revokeRole.isPending ? "Revoking…" : "Revoke role"}
                </button>
              )}
            </div>
            {assignRole.isError && <p className="mt-2 text-sm text-[var(--clay-red)]">{assignRole.error.message}</p>}
            {assignRole.isSuccess && <p className="mt-2 text-sm" style={{ color: "var(--forest)" }}>Role assigned.</p>}
            {revokeRole.isError && <p className="mt-2 text-sm text-[var(--clay-red)]">{revokeRole.error.message}</p>}
            {revokeRole.isSuccess && <p className="mt-2 text-sm" style={{ color: "var(--forest)" }}>Role revoked — back to Community Member.</p>}
          </section>
        )}

        <section className="flex flex-col items-center rounded-sm border border-[var(--rule)] bg-white p-6">
          <h2 className="font-display text-lg">Digital membership card</h2>
          {card && (
            <div className="mt-4 w-full max-w-xs rounded-sm border border-[var(--rule)] bg-[var(--surface)] p-5 text-center">
              {card.photo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={card.photo_url} alt="" className="mx-auto h-20 w-20 rounded-full object-cover" />
              ) : (
                <div className="mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-white font-display text-2xl text-[var(--ink-soft)]">
                  {card.full_name.charAt(0)}
                </div>
              )}
              <p className="font-display mt-3 text-lg">{card.full_name}</p>
              <p className="font-mono text-xs text-[var(--ink-soft)]">{card.membership_number}</p>
              <p className="text-xs text-[var(--ink-soft)]">{card.family_name ?? "No family"}</p>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={`data:image/png;base64,${card.qr_code_base64}`}
                alt="Membership QR code"
                className="mx-auto mt-4 h-32 w-32"
              />
              <p className="mt-2 font-mono text-xs text-[var(--ink-soft)]">Nsaabodeɛ Smart · Bodi Anidasoɔ</p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-[var(--rule)] pb-2">
      <dt className="text-[var(--ink-soft)]">{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
