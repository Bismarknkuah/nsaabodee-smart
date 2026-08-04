"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { tenantsApi } from "@/lib/api/tenants";

/**
 * "Managing platform administrators." Every account created here goes
 * through the same path as the CLI's create_platform_admin command —
 * role=platform_admin only, deliberately never a Django superuser,
 * since that would bypass every operational boundary a Platform Admin
 * is supposed to respect (no adding/editing members, no managing a
 * community's finances, and so on).
 */
export default function PlatformAdminsPage() {
  const qc = useQueryClient();
  const { data: admins, isLoading, error } = useQuery({ queryKey: ["platform-admins"], queryFn: tenantsApi.listPlatformAdmins });
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
            <h1 className="font-display text-4xl">Platform Administrators</h1>
            <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
              Everyone with cross-community, platform-wide access. Each account&apos;s authority
              comes entirely from this role — never a superuser bypass — so every operational
              boundary a Platform Admin is meant to respect still applies.
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

        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
        {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}

        <ol className="divide-y divide-[var(--rule)] border-y-2 border-[var(--ink)]">
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
      </main>
    </div>
  );
}
