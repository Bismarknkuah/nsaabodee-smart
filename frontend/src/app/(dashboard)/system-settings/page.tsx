"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { tenantsApi } from "@/lib/api/tenants";
import { accountsApi } from "@/lib/api/accounts";
import { useFamilies } from "@/lib/hooks/useFamilies";
import { useAuthStore } from "@/store/authStore";
import { formatRole } from "@/lib/formatRole";

/**
 * 'The user management should stand on its own and the system
 * settings should stand on its own. Update the system settings for
 * the community admin, family head, and the town leader for them to
 * manage their jurisdiction — let it have more options for them to
 * select what each user role has to see on their dashboard or has to
 * have access to.'
 *
 * User Management (a separate page) is now purely about WHO holds
 * which role — assigning, revoking, suspending. This page is purely
 * about WHAT a role, once held, can see and do. The same page for a
 * Platform Admin and everyone else, deliberately: each already had
 * their own "restrict what an account can do" concept before this
 * turn (Platform Admin's own capability flags; everyone else's
 * per-account disabled_features), and this just gives both concepts
 * the same, single, well-named home instead of splitting "system
 * settings" across two differently-named pages depending on who's
 * looking.
 */
export default function SystemSettingsPage() {
  const currentUser = useAuthStore((s) => s.user);
  const isPlatformAdmin = currentUser?.role === "platform_admin" || currentUser?.is_superuser;

  return isPlatformAdmin ? <PlatformAdminSystemSettings /> : <JurisdictionSystemSettings />;
}

function PlatformAdminSystemSettings() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["platform-admin-capabilities"], queryFn: tenantsApi.getPlatformAdminCapabilities });

  const update = useMutation({
    mutationFn: ({ targetId, capabilities }: { targetId: string; capabilities: Record<string, boolean> }) =>
      tenantsApi.updatePlatformAdminCapabilities(targetId, capabilities),
    onMutate: async ({ targetId, capabilities }) => {
      await qc.cancelQueries({ queryKey: ["platform-admin-capabilities"] });
      const previous = qc.getQueryData<{ capability_definitions: Record<string, string>; admins: { id: string; username: string; is_you: boolean; capabilities: Record<string, boolean> }[] }>(["platform-admin-capabilities"]);
      if (previous) {
        qc.setQueryData(["platform-admin-capabilities"], {
          ...previous,
          admins: previous.admins.map((a) => (a.id === targetId ? { ...a, capabilities: { ...a.capabilities, ...capabilities } } : a)),
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(["platform-admin-capabilities"], context.previous);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["platform-admin-capabilities"] }),
  });

  return (
    <div className="font-body min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--text-soft)]">Platform Administration</p>
        <h1 className="font-display mt-1 text-4xl">System Settings</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--text-soft)]">
          Restrict what each Platform Admin account can do. A capability left on means that
          account keeps full access to it — nothing here is retroactively restrictive by default.
        </p>
      </header>

      <main className="px-8 py-8">
        {isLoading && <p className="text-sm text-[var(--text-soft)]">Loading…</p>}
        {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}

        {data && (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr className="border-b-2 border-[var(--ink)]">
                  <th className="py-2 pr-4 text-left font-medium">Platform Admin</th>
                  {Object.entries(data.capability_definitions).map(([key, description]) => (
                    <th key={key} className="px-3 py-2 text-left font-medium" title={description}>
                      {key.replace(/_/g, " ")}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.admins.map((admin) => (
                  <tr key={admin.id} className="border-b border-[var(--border)]">
                    <td className="py-3 pr-4 font-medium">
                      {admin.username}
                      {admin.is_you && <span className="ml-2 text-xs text-[var(--text-soft)]">(you)</span>}
                    </td>
                    {Object.keys(data.capability_definitions).map((key) => (
                      <td key={key} className="px-3 py-3">
                        <input
                          type="checkbox"
                          checked={admin.capabilities[key]}
                          disabled={admin.is_you}
                          onChange={(e) =>
                            update.mutate({ targetId: admin.id, capabilities: { [key]: e.target.checked } })
                          }
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {update.isError && <p className="mt-3 text-sm text-[var(--clay-red)]">{update.error.message}</p>}
          </div>
        )}
      </main>
    </div>
  );
}

function JurisdictionSystemSettings() {
  const currentUser = useAuthStore((s) => s.user);
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["manageable-users"], queryFn: accountsApi.manageableUsers });
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const update = useMutation({
    mutationFn: ({ targetId, disabledFeatures }: { targetId: string; disabledFeatures: string[] }) =>
      accountsApi.setDisabledFeatures(targetId, disabledFeatures),
    onMutate: async ({ targetId, disabledFeatures }) => {
      await qc.cancelQueries({ queryKey: ["manageable-users"] });
      const previous = qc.getQueryData<ManageableUsersData>(["manageable-users"]);
      if (previous) {
        qc.setQueryData(["manageable-users"], {
          ...previous,
          users: previous.users.map((u) => (u.id === targetId ? { ...u, disabled_features: disabledFeatures } : u)),
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(["manageable-users"], context.previous);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["manageable-users"] }),
  });

  const isFamilyHead = currentUser?.role === "family_head";
  const isChief = currentUser?.role === "traditional_leader";

  return (
    <div className="font-body min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--text-soft)]">
          {isFamilyHead ? "Family" : isChief ? "Town Elders" : "Community"} Administration
        </p>
        <h1 className="font-display mt-1 text-4xl">System Settings</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--text-soft)]">
          What each of your {isFamilyHead ? "family's" : isChief ? "Town Elders'" : "community's"} own
          accounts can see and do on their own dashboard. Restricting a feature only ever takes
          something away — it can never grant more than that person's role already allows.
        </p>
      </header>

      <main className="px-8 py-8">
        {isLoading && <p className="text-sm text-[var(--text-soft)]">Loading…</p>}
        {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}

        {data && !isChief && (
          <BulkFeatureApplySection
            restrictableFeatures={data.restrictable_features}
            isFamilyHead={isFamilyHead}
            ownFamilyId={data.own_family_id}
          />
        )}

        {data && data.users.length === 0 && (
          <p className="mt-4 text-sm text-[var(--text-soft)]">Nothing to configure yet.</p>
        )}

        {data && data.users.length > 0 && (
          <ul className="mt-4 divide-y divide-[var(--rule)] border-y-2 border-[var(--ink)]">
            {data.users.map((u) => (
              <li key={u.id} className="py-4">
                <button onClick={() => setExpandedId(expandedId === u.id ? null : u.id)} className="flex w-full items-center justify-between text-left">
                  <div>
                    <p className="text-sm font-medium">{u.username}</p>
                    <p className="text-xs text-[var(--text-soft)]">
                      {formatRole(u.role)}
                      {u.community_name && ` · ${u.community_name}`}
                      {u.disabled_features.length > 0 && ` · ${u.disabled_features.length} feature(s) restricted`}
                    </p>
                  </div>
                  <span className="text-xs text-[var(--text-soft)]">{expandedId === u.id ? "Close" : "Manage"}</span>
                </button>
                {expandedId === u.id && (
                  <FeatureToggleList
                    restrictableFeatures={data.restrictable_features}
                    disabledFeatures={u.disabled_features}
                    onToggle={(features) => update.mutate({ targetId: u.id, disabledFeatures: features })}
                  />
                )}
              </li>
            ))}
          </ul>
        )}
        {update.isError && <p className="mt-3 text-sm text-[var(--clay-red)]">{update.error.message}</p>}
      </main>
    </div>
  );
}

interface ManageableUsersData {
  restrictable_features: Record<string, string>;
  own_family_id: string | null;
  own_family_name: string | null;
  users: { id: string; username: string; role: string; community_name: string | null; disabled_features: string[]; is_active: boolean; member_id: string | null }[];
}

/**
 * "The community admin can should have options where he can apply
 * changes for some family and can also set for all members." A
 * Family Head sees only "apply to my whole family" (their own
 * restrictable set); a Community Admin sees both "apply to a family"
 * and "apply to all members" — always applying exactly the same
 * restrictable_features list, and always re-checked per-target
 * against the same authority rule the single-account toggle above
 * already uses.
 */
function BulkFeatureApplySection({
  restrictableFeatures,
  isFamilyHead,
  ownFamilyId,
}: {
  restrictableFeatures: Record<string, string>;
  isFamilyHead: boolean;
  ownFamilyId: string | null;
}) {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [pickedFamilyId, setPickedFamilyId] = useState("");
  const [result, setResult] = useState<string | null>(null);

  const { data: families } = useFamilies();

  const applyToFamily = useMutation({
    mutationFn: (familyId: string) => accountsApi.setDisabledFeaturesForFamily(familyId, selected),
    onSuccess: (data) => setResult(`Applied to ${data.updated_count} member(s) of that family.`),
  });

  const applyToAllMembers = useMutation({
    mutationFn: () => accountsApi.setDisabledFeaturesForAllMembers(selected),
    onSuccess: (data) => setResult(`Applied to ${data.updated_count} member(s) across the community.`),
  });

  const toggle = (href: string) => {
    setResult(null);
    setSelected((prev) => (prev.includes(href) ? prev.filter((f) => f !== href) : [...prev, href]));
  };

  return (
    <div className="border border-[var(--border)] p-4">
      <button onClick={() => setOpen((v) => !v)} className="text-sm font-medium text-[var(--forest)]">
        {open ? "Hide bulk settings" : "Apply settings in bulk →"}
      </button>
      {open && (
        <div className="mt-3 space-y-3">
          <p className="text-xs text-[var(--text-soft)]">
            Pick which features to restrict, then apply them to everyone in one action — instead of
            one account at a time below.
          </p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {Object.entries(restrictableFeatures).map(([href, label]) => (
              <label key={href} className="flex items-center gap-2 text-xs">
                <input type="checkbox" checked={selected.includes(href)} onChange={() => toggle(href)} />
                {label}
              </label>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {isFamilyHead && ownFamilyId && (
              <button
                onClick={() => applyToFamily.mutate(ownFamilyId)}
                disabled={applyToFamily.isPending}
                className="rounded-sm bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
              >
                {applyToFamily.isPending ? "Applying…" : "Apply to my whole family"}
              </button>
            )}
            {!isFamilyHead && (
              <>
                <select
                  value={pickedFamilyId} onChange={(e) => setPickedFamilyId(e.target.value)}
                  className="rounded-sm border border-[var(--border)] px-2 py-1.5 text-xs"
                >
                  <option value="">Choose a family…</option>
                  {families?.filter((f) => f.status === "active").map((f) => (
                    <option key={f.id} value={f.id}>{f.name}</option>
                  ))}
                </select>
                <button
                  onClick={() => applyToFamily.mutate(pickedFamilyId)}
                  disabled={applyToFamily.isPending || !pickedFamilyId}
                  className="rounded-sm border border-[var(--border)] px-3 py-1.5 text-xs font-medium disabled:opacity-60"
                >
                  {applyToFamily.isPending ? "Applying…" : "Apply to that family"}
                </button>
                <button
                  onClick={() => applyToAllMembers.mutate()}
                  disabled={applyToAllMembers.isPending}
                  className="rounded-sm bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
                >
                  {applyToAllMembers.isPending ? "Applying…" : "Apply to all community members"}
                </button>
              </>
            )}
          </div>
          {(applyToFamily.isError || applyToAllMembers.isError) && (
            <p className="text-xs text-[var(--clay-red)]">{((applyToFamily.error ?? applyToAllMembers.error) as Error).message}</p>
          )}
          {result && <p className="text-xs" style={{ color: "var(--forest)" }}>{result}</p>}
        </div>
      )}
    </div>
  );
}

function FeatureToggleList({
  restrictableFeatures,
  disabledFeatures,
  onToggle,
}: {
  restrictableFeatures: Record<string, string>;
  disabledFeatures: string[];
  onToggle: (features: string[]) => void;
}) {
  return (
    <div className="mt-3 rounded-sm bg-[var(--surface)] p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-soft)]">
        Checked = visible on their dashboard
      </p>
      <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
        {Object.entries(restrictableFeatures).map(([href, label]) => {
          const isEnabled = !disabledFeatures.includes(href);
          return (
            <label key={href} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isEnabled}
                onChange={(e) => {
                  const next = e.target.checked
                    ? disabledFeatures.filter((f) => f !== href)
                    : [...disabledFeatures, href];
                  onToggle(next);
                }}
              />
              {label}
            </label>
          );
        })}
      </div>
    </div>
  );
}
