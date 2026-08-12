"use client";

import "@/styles/family-registry-tokens.css";
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { tenantsApi } from "@/lib/api/tenants";

/**
 * "Administrator Autonomy... sufficient permissions to customize
 * their workspace... without depending on the platform Administrator
 * for routine changes." Everything on this page is Community-Admin
 * self-service — no Platform Admin involvement anywhere in this flow.
 */
export default function CommunitySettingsPage() {
  const qc = useQueryClient();
  const { data: community, isLoading } = useQuery({ queryKey: ["my-community-branding"], queryFn: tenantsApi.getMyCommunityBranding });

  const [tagline, setTagline] = useState("");
  const [primaryColor, setPrimaryColor] = useState("");
  const [secondaryColor, setSecondaryColor] = useState("");
  const [requiredApprovals, setRequiredApprovals] = useState("2");

  useEffect(() => {
    if (community) {
      setTagline(community.tagline ?? "");
      setPrimaryColor(community.primary_color ?? "");
      setSecondaryColor(community.secondary_color ?? "");
      setRequiredApprovals(String(community.required_funeral_approvals ?? 2));
    }
  }, [community]);

  const updateBranding = useMutation({
    mutationFn: () => tenantsApi.updateMyCommunityBranding({ tagline, primary_color: primaryColor, secondary_color: secondaryColor }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-community-branding"] }),
  });

  const updateWorkflow = useMutation({
    mutationFn: () => tenantsApi.updateMyApprovalWorkflow(Number(requiredApprovals)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["my-community-branding"] }),
  });

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Your Workspace</p>
        <h1 className="font-display mt-1 text-4xl">Community Settings</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Configure your own community&apos;s workspace directly — branding and approval workflow,
          with no need to involve the Platform Administrator for either.
        </p>
      </header>

      <main className="grid max-w-4xl gap-6 px-8 py-8 sm:grid-cols-2">
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}

        <section className="rounded-sm border border-[var(--rule)] bg-white p-5">
          <h2 className="font-display text-xl">Branding</h2>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">Your community&apos;s tagline and color scheme.</p>

          <div className="mt-4 space-y-3">
            <div>
              <label className="text-xs font-medium">Tagline</label>
              <input
                value={tagline} onChange={(e) => setTagline(e.target.value)} placeholder="e.g. Every ledger transparent."
                className="mt-1 w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
              />
            </div>
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="text-xs font-medium">Primary color</label>
                <div className="mt-1 flex items-center gap-2">
                  <input
                    value={primaryColor} onChange={(e) => setPrimaryColor(e.target.value)} placeholder="#2F5233"
                    className="w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
                  />
                  {primaryColor && /^#[0-9A-Fa-f]{6}$/.test(primaryColor) && (
                    <span className="h-8 w-8 shrink-0 rounded-sm border border-[var(--rule)]" style={{ backgroundColor: primaryColor }} />
                  )}
                </div>
              </div>
              <div className="flex-1">
                <label className="text-xs font-medium">Secondary color</label>
                <div className="mt-1 flex items-center gap-2">
                  <input
                    value={secondaryColor} onChange={(e) => setSecondaryColor(e.target.value)} placeholder="#B8860B"
                    className="w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
                  />
                  {secondaryColor && /^#[0-9A-Fa-f]{6}$/.test(secondaryColor) && (
                    <span className="h-8 w-8 shrink-0 rounded-sm border border-[var(--rule)]" style={{ backgroundColor: secondaryColor }} />
                  )}
                </div>
              </div>
            </div>
            {updateBranding.isError && <p className="text-sm text-[var(--clay-red)]">{updateBranding.error.message}</p>}
            {updateBranding.isSuccess && <p className="text-sm" style={{ color: "var(--forest)" }}>Branding saved.</p>}
            <button
              onClick={() => updateBranding.mutate()}
              disabled={updateBranding.isPending}
              className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {updateBranding.isPending ? "Saving…" : "Save branding"}
            </button>
            <p className="text-xs text-[var(--ink-soft)]">
              Logo upload isn&apos;t available from this page yet — contact support if you need your logo updated in the meantime.
            </p>
          </div>
        </section>

        <section className="rounded-sm border border-[var(--rule)] bg-white p-5">
          <h2 className="font-display text-xl">Approval Workflow</h2>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">
            How many distinct community leaders must approve a requested funeral opening before it goes live.
          </p>

          <div className="mt-4 space-y-3">
            <div>
              <label className="text-xs font-medium">Required approvals</label>
              <input
                type="number" min={1} max={10} value={requiredApprovals}
                onChange={(e) => setRequiredApprovals(e.target.value)}
                className="mt-1 w-32 rounded-sm border border-[var(--rule)] px-3 py-2 text-sm"
              />
            </div>
            {updateWorkflow.isError && <p className="text-sm text-[var(--clay-red)]">{updateWorkflow.error.message}</p>}
            {updateWorkflow.isSuccess && <p className="text-sm" style={{ color: "var(--forest)" }}>Approval workflow saved.</p>}
            <button
              onClick={() => updateWorkflow.mutate()}
              disabled={updateWorkflow.isPending}
              className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {updateWorkflow.isPending ? "Saving…" : "Save workflow"}
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}
