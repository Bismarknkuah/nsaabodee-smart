"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { tenantsApi } from "@/lib/api/tenants";

/**
 * "User Management" — 'they can manage the platform admins on the
 * community admins... they manage only the platform admin, not
 * community member.' Two sections, deliberately never a third for
 * ordinary community members — that stays each Community Admin's own
 * responsibility, never Platform Admin's.
 */
export default function PlatformAdminsPage() {
  const qc = useQueryClient();
  const { data: admins, isLoading, error } = useQuery({ queryKey: ["platform-admins"], queryFn: tenantsApi.listPlatformAdmins });
  const { data: communityAdmins, isLoading: communityAdminsLoading, error: communityAdminsError } = useQuery({
    queryKey: ["all-community-admins"], queryFn: tenantsApi.listAllCommunityAdmins,
  });
  const [showForm, setShowForm] = useState(false);
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const addAdmin = useMutation({
    mutationFn: () => tenantsApi.addPlatformAdmin({ username, password, email: email || undefined }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["platform-admins"] });
      setUsername(""); setEmail(""); setPassword(""); setShowForm(false);
    },
  });

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Platform Administration</p>
        <div className="mt-1 flex items-start justify-between gap-4">
          <div>
            <h1 className="font-display text-4xl">User Management</h1>
            <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
              Every Platform Admin and every Community Admin, platform-wide. Deliberately never
              ordinary community members here — each Community Admin keeps that authority for
              their own community.
            </p>
          </div>
          <button onClick={() => setShowForm((s) => !s)} className="shrink-0 bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white">
            {showForm ? "Cancel" : "Add Platform Admin"}
          </button>
        </div>
      </header>

      <main className="px-8 py-8">
        {showForm && (
          <form
            onSubmit={(e) => { e.preventDefault(); addAdmin.mutate(); }}
            className="mb-6 grid grid-cols-3 gap-3 rounded-sm bg-[var(--surface)] p-4"
          >
            <input
              value={username} onChange={(e) => setUsername(e.target.value)} placeholder="Username"
              className="rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
            />
            <input
              value={email} onChange={(e) => setEmail(e.target.value)} placeholder="Email (optional)"
              className="rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
            />
            <input
              type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password"
              className="rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
            />
            {addAdmin.isError && <p className="col-span-3 text-sm text-[var(--clay-red)]">{addAdmin.error.message}</p>}
            <button
              type="submit"
              disabled={addAdmin.isPending || !username.trim() || password.length < 8}
              className="col-span-3 rounded-sm bg-[var(--ink)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {addAdmin.isPending ? "Creating…" : "Create Platform Admin"}
            </button>
          </form>
        )}

        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Platform Administrators</p>
        {isLoading && <p className="mt-2 text-sm text-[var(--ink-soft)]">Loading…</p>}
        {error && <p className="mt-2 text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}

        <ol className="mt-2 divide-y divide-[var(--rule)] border-y-2 border-[var(--ink)]">
          {admins?.map((a, i) => (
            <li key={a.id} className="flex items-center gap-3 py-3">
              <span className="font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(2, "0")}</span>
              <div>
                <p className="text-sm font-medium">{a.username}</p>
                {a.email && <p className="text-xs text-[var(--ink-soft)]">{a.email}</p>}
              </div>
            </li>
          ))}
        </ol>

        <p className="mt-10 font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
          Community Administrators · {communityAdmins?.length ?? 0} across every community
        </p>
        {communityAdminsLoading && <p className="mt-2 text-sm text-[var(--ink-soft)]">Loading…</p>}
        {communityAdminsError && <p className="mt-2 text-sm text-[var(--clay-red)]">{(communityAdminsError as Error).message}</p>}

        <ol className="mt-2 divide-y divide-[var(--rule)] border-y-2 border-[var(--ink)]">
          {communityAdmins?.map((a, i) => (
            <li key={a.id} className="flex items-center gap-3 py-3">
              <span className="font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(2, "0")}</span>
              <div>
                <p className="text-sm font-medium">{a.username}</p>
                <p className="text-xs text-[var(--ink-soft)]">
                  {a.community_name ?? "No community"}{a.email && ` · ${a.email}`}
                </p>
              </div>
            </li>
          ))}
          {communityAdmins?.length === 0 && (
            <li className="py-3 text-sm text-[var(--ink-soft)]">No Community Admin accounts exist yet.</li>
          )}
        </ol>
      </main>
    </div>
  );
}
