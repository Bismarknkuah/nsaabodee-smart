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

      <div className="max-w-4xl px-8 pb-8">
        <DataBackupSection />
      </div>
    </div>
  );
}

/**
 * "Each community admin will have a section... where they can import
 * a Google Drive link they want to back up their system data to, and
 * should also have options to retrieve them back." No OAuth to
 * Google Drive here — download the backup file, save it to your own
 * Drive as "anyone with the link", and paste that same link back in
 * later to restore it.
 */
function DataBackupSection() {
  const qc = useQueryClient();
  const [driveLink, setDriveLink] = useState("");
  const [restoreFile, setRestoreFile] = useState<File | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const { data: history } = useQuery({ queryKey: ["my-community-backup-history"], queryFn: tenantsApi.myCommunityBackupHistory });

  const download = useMutation({
    mutationFn: () => tenantsApi.downloadMyCommunityBackup(),
    onSuccess: () => { setDownloadError(null); qc.invalidateQueries({ queryKey: ["my-community-backup-history"] }); },
    onError: (err: Error) => setDownloadError(err.message),
  });

  const restore = useMutation({
    mutationFn: () => tenantsApi.restoreMyCommunityBackup(driveLink),
    onSuccess: () => { setDriveLink(""); qc.invalidateQueries({ queryKey: ["my-community-backup-history"] }); },
  });

  const restoreFromFile = useMutation({
    mutationFn: () => tenantsApi.restoreMyCommunityBackupFromFile(restoreFile!),
    onSuccess: () => { setRestoreFile(null); qc.invalidateQueries({ queryKey: ["my-community-backup-history"] }); },
  });

  return (
    <section className="rounded-sm border border-[var(--rule)] bg-white p-5">
      <h2 className="font-display text-xl">Data Backup</h2>
      <p className="mt-1 text-sm text-[var(--ink-soft)]">
        Back up your community&apos;s members and families to a file you keep — on your own
        Google Drive, or anywhere else — and bring them back later if you ever need to.
      </p>

      <div className="mt-4 grid gap-6 sm:grid-cols-2">
        <div>
          <h3 className="text-sm font-medium">Back up now</h3>
          <p className="mt-1 text-xs text-[var(--ink-soft)]">
            Downloads a file to your device. Save it to Google Drive yourself, then share it
            as &quot;Anyone with the link&quot; so you can restore from it later.
          </p>
          <button
            onClick={() => download.mutate()}
            disabled={download.isPending}
            className="mt-2 rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {download.isPending ? "Preparing…" : "Download backup"}
          </button>
          {downloadError && <p className="mt-2 text-sm text-[var(--clay-red)]">{downloadError}</p>}
        </div>

        <div>
          <h3 className="text-sm font-medium">Restore from Google Drive</h3>
          <p className="mt-1 text-xs text-[var(--ink-soft)]">
            Paste the share link to a backup file you previously saved to Drive. Existing
            records are matched and updated — nothing is duplicated or deleted.
          </p>
          <div className="mt-2 flex gap-2">
            <input
              value={driveLink} onChange={(e) => setDriveLink(e.target.value)}
              placeholder="https://drive.google.com/file/d/…"
              className="flex-1 rounded-sm border border-[var(--rule)] px-3 py-2 text-sm outline-none focus:border-[var(--forest)]"
            />
            <button
              onClick={() => restore.mutate()}
              disabled={restore.isPending || !driveLink.trim()}
              className="rounded-sm border border-[var(--rule)] px-4 py-2 text-sm font-medium disabled:opacity-60"
            >
              {restore.isPending ? "Restoring…" : "Restore"}
            </button>
          </div>
          {restore.isError && <p className="mt-2 text-sm text-[var(--clay-red)]">{(restore.error as Error).message}</p>}
          {restore.isSuccess && (
            <p className="mt-2 text-sm" style={{ color: "var(--forest)" }}>
              Restored: {restore.data.families_restored} famil{restore.data.families_restored === 1 ? "y" : "ies"},{" "}
              {restore.data.members_created} new member{restore.data.members_created === 1 ? "" : "s"}, {restore.data.members_updated} updated.
              {restore.data.member_errors.length > 0 && ` ${restore.data.member_errors.length} row(s) had issues.`}
            </p>
          )}

          {/* "Should also be able to upload from my computer to synchronize." */}
          <div className="mt-4 border-t border-dashed border-[var(--rule)] pt-4">
            <h3 className="text-sm font-medium">Or restore from a file on this computer</h3>
            <p className="mt-1 text-xs text-[var(--ink-soft)]">
              Already have a backup file saved locally? Upload it directly — no Google Drive needed.
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <input
                type="file" accept="application/json,.json"
                onChange={(e) => setRestoreFile(e.target.files?.[0] ?? null)}
                className="text-sm"
              />
              <button
                onClick={() => restoreFromFile.mutate()}
                disabled={restoreFromFile.isPending || !restoreFile}
                className="rounded-sm border border-[var(--rule)] px-4 py-2 text-sm font-medium disabled:opacity-60"
              >
                {restoreFromFile.isPending ? "Restoring…" : "Restore from file"}
              </button>
            </div>
            {restoreFromFile.isError && <p className="mt-2 text-sm text-[var(--clay-red)]">{(restoreFromFile.error as Error).message}</p>}
            {restoreFromFile.isSuccess && (
              <p className="mt-2 text-sm" style={{ color: "var(--forest)" }}>
                Restored: {restoreFromFile.data.families_restored} famil{restoreFromFile.data.families_restored === 1 ? "y" : "ies"},{" "}
                {restoreFromFile.data.members_created} new member{restoreFromFile.data.members_created === 1 ? "" : "s"}, {restoreFromFile.data.members_updated} updated.
                {restoreFromFile.data.member_errors.length > 0 && ` ${restoreFromFile.data.member_errors.length} row(s) had issues.`}
              </p>
            )}
          </div>
        </div>
      </div>

      {history && history.length > 0 && (
        <div className="mt-6 border-t border-[var(--rule)] pt-4">
          <h3 className="text-sm font-medium">History</h3>
          <div className="mt-2 space-y-1 text-xs text-[var(--ink-soft)]">
            {history.map((h) => (
              <p key={h.id}>
                {h.kind === "export" ? "Backed up" : "Restored"} {h.member_count} member(s), {h.family_count} famil{h.family_count === 1 ? "y" : "ies"}
                {h.performed_by_username ? ` by ${h.performed_by_username}` : ""} — {new Date(h.created_at).toLocaleString()}
              </p>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
