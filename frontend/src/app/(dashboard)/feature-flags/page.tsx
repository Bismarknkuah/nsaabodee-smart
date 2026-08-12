"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { tenantsApi } from "@/lib/api/tenants";

export default function FeatureFlagsPage() {
  const qc = useQueryClient();
  const { data: flags, isLoading } = useQuery({ queryKey: ["feature-flags"], queryFn: tenantsApi.listFeatureFlags });
  const toggle = useMutation({
    mutationFn: ({ key, isEnabled }: { key: string; isEnabled: boolean }) => tenantsApi.toggleFeatureFlag(key, isEnabled),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["feature-flags"] }),
  });

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Platform Administration</p>
        <h1 className="font-display mt-1 text-4xl">Feature Flags</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          A genuine kill-switch, not a toy — turning one off actually disables that feature
          platform-wide immediately, for every community.
        </p>
      </header>

      <main className="px-8 py-8">
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
        <ol className="divide-y divide-[var(--rule)] border-y-2 border-[var(--ink)]">
          {flags?.map((f, i) => (
            <li key={f.id} className="flex items-center justify-between gap-4 py-4">
              <div className="flex items-baseline gap-3">
                <span className="font-mono text-xs text-[var(--ink-soft)]">{String(i + 1).padStart(2, "0")}</span>
                <div>
                  <p className="font-medium">{f.name}</p>
                  <p className="text-xs text-[var(--ink-soft)]">{f.description}</p>
                </div>
              </div>
              <button
                onClick={() => toggle.mutate({ key: f.key, isEnabled: !f.is_enabled })}
                disabled={toggle.isPending}
                className="shrink-0 border px-4 py-1.5 text-xs font-medium disabled:opacity-60"
                style={
                  f.is_enabled
                    ? { borderColor: "var(--forest)", color: "var(--forest)" }
                    : { borderColor: "var(--clay-red)", color: "var(--clay-red)" }
                }
              >
                {f.is_enabled ? "On — click to disable" : "Off — click to enable"}
              </button>
            </li>
          ))}
        </ol>
      </main>
    </div>
  );
}
