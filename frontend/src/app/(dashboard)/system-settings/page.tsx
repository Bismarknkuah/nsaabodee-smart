"use client";

import "@/styles/family-registry-tokens.css";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { tenantsApi } from "@/lib/api/tenants";

/**
 * 'System settings should provide more option that will restrict or
 * give access to the platform admin based on what they can do.' Every
 * toggle here is real — it calls the exact same backend check the
 * real action itself enforces, not a cosmetic setting. A Platform
 * Admin's own row is shown but never editable here (see the backend's
 * own self-lockout protection in update_platform_admin_capabilities) —
 * ask a different Platform Admin to change yours.
 */
export default function SystemSettingsPage() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["platform-admin-capabilities"], queryFn: tenantsApi.getPlatformAdminCapabilities });

  const update = useMutation({
    mutationFn: ({ targetId, capabilities }: { targetId: string; capabilities: Record<string, boolean> }) =>
      tenantsApi.updatePlatformAdminCapabilities(targetId, capabilities),
    // 'The system setting should be more advanced and can save when
    // it's ticked or selected' — the checkbox reflects the new state
    // the instant it's clicked, not after a full round trip. If the
    // save genuinely fails, onError rolls the cache back to exactly
    // what it held before, so the checkbox snaps back rather than
    // silently disagreeing with the server.
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
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Platform Administration</p>
        <h1 className="font-display mt-1 text-4xl">System Settings</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Restrict what each Platform Admin account can do. A capability left on means that
          account keeps full access to it — nothing here is retroactively restrictive by default.
        </p>
      </header>

      <main className="px-8 py-8">
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
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
                  <tr key={admin.id} className="border-b border-[var(--rule)]">
                    <td className="py-3 pr-4 font-medium">
                      {admin.username}
                      {admin.is_you && <span className="ml-2 text-xs text-[var(--ink-soft)]">(you)</span>}
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
