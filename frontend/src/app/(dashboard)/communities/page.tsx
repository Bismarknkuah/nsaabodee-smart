"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { tenantsApi, type Community } from "@/lib/api/tenants";
import { homepageImagesApi } from "@/lib/api/homepageImages";
import { planInterestApi } from "@/lib/api/planInterest";
import { announcementsApi } from "@/lib/api/announcements";
import { useAuthStore } from "@/store/authStore";

export default function CommunitiesConsolePage() {
  const user = useAuthStore((s) => s.user);
  const isPlatformAdmin = user?.is_superuser || user?.role === "platform_admin";

  const { data: communities, isLoading, isError } = useQuery({
    queryKey: ["communities"],
    queryFn: tenantsApi.list,
    enabled: isPlatformAdmin,
    retry: false,
  });
  const [showCreate, setShowCreate] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  if (!isPlatformAdmin) {
    return (
      <div className="font-body min-h-screen bg-[var(--paper)] px-8 py-16 text-center text-[var(--ink)]">
        <p className="font-display text-xl">Platform administrators only</p>
        <p className="mt-2 text-sm text-[var(--ink-soft)]">
          Your own community&apos;s admin still manages everything about your community day to
          day — creating, editing, or removing a community itself is a platform-level action.
        </p>
      </div>
    );
  }

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Platform Administration</p>
        <div className="mt-1 flex items-center justify-between">
          <h1 className="font-display text-4xl">Communities</h1>
          <button
            onClick={() => setShowCreate(true)}
            className="bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white"
          >
            + New community
          </button>
        </div>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Every community here is completely isolated — its own families, members, funerals,
          and money, invisible to every other one. Each runs its own affairs through its own
          Community Admin once created.
        </p>
      </header>

      <main className="px-8 py-8">
        <HomepageImagesSection />
        <div className="mt-6"><PlanInterestSection /></div>
        <div className="mt-6"><AnnouncementReviewSection /></div>

        <h2 className="font-display mt-10 mb-3 text-xl">Communities</h2>
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
        {isError && <p className="text-sm text-[var(--clay-red)]">Could not load communities.</p>}

        <ul className="divide-y divide-[var(--rule)] border-y border-[var(--rule)]">
          {communities?.map((c) => (
            <li key={c.id}>
              <button
                onClick={() => setExpandedId(expandedId === c.id ? null : c.id)}
                className="flex w-full items-center justify-between py-4 text-left"
              >
                <div>
                  <p className="font-medium">
                    {c.name}
                    {!c.is_active && (
                      <span className="ml-2 rounded-full bg-[var(--surface)] px-2 py-0.5 text-xs text-[var(--ink-soft)]">deactivated</span>
                    )}
                    {c.access_expires_at && (
                      <span className={`ml-2 rounded-full px-2 py-0.5 text-xs ${c.is_access_expired ? "bg-[var(--clay-red)]/10 text-[var(--clay-red)]" : "bg-[var(--gold)]/15 text-[var(--gold)]"}`}>
                        {c.is_access_expired ? "access expired" : `${c.access_days_remaining}d left`}
                      </span>
                    )}
                  </p>
                  <p className="font-mono text-xs text-[var(--ink-soft)]">{c.slug} · {c.region || "no region set"}</p>
                </div>
                <span className="text-xs text-[var(--ink-soft)]">{expandedId === c.id ? "Hide ▲" : "Manage ▼"}</span>
              </button>
              {expandedId === c.id && <CommunityDetailPanel community={c} />}
            </li>
          ))}
        </ul>
      </main>

      {showCreate && <CreateCommunityDialog onClose={() => setShowCreate(false)} />}
    </div>
  );
}

function CommunityDetailPanel({ community }: { community: Community }) {
  const qc = useQueryClient();
  const [name, setName] = useState(community.name);
  const [region, setRegion] = useState(community.region);
  const [maleRate, setMaleRate] = useState(community.default_general_male_amount);
  const [femaleRate, setFemaleRate] = useState(community.default_general_female_amount);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["communities"] });

  const update = useMutation({
    mutationFn: () => tenantsApi.update(community.id, {
      name, region, default_general_male_amount: maleRate, default_general_female_amount: femaleRate,
    }),
    onSuccess: invalidate,
  });
  const deactivate = useMutation({ mutationFn: () => tenantsApi.deactivate(community.id), onSuccess: invalidate });
  const reactivate = useMutation({ mutationFn: () => tenantsApi.reactivate(community.id), onSuccess: invalidate });
  const remove = useMutation({
    mutationFn: () => tenantsApi.deleteEmpty(community.id),
    onSuccess: invalidate,
    onError: (err: Error) => setDeleteError(err.message),
  });
  const [extendDays, setExtendDays] = useState("30");
  const extendAccess = useMutation({ mutationFn: () => tenantsApi.extendAccess(community.id, Number(extendDays)), onSuccess: invalidate });
  const makePermanent = useMutation({ mutationFn: () => tenantsApi.makePermanent(community.id), onSuccess: invalidate });
  const terminateAccess = useMutation({ mutationFn: () => tenantsApi.terminateAccess(community.id), onSuccess: invalidate });

  const { data: admins } = useQuery({ queryKey: ["community-admins", community.id], queryFn: () => tenantsApi.listAdmins(community.id) });
  const [showAddAdmin, setShowAddAdmin] = useState(false);

  return (
    <div className="mb-4 space-y-4 rounded-sm bg-[var(--surface)] p-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-[var(--ink-soft)]">Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-1.5 text-sm" />
        </div>
        <div>
          <label className="text-xs text-[var(--ink-soft)]">Region</label>
          <input value={region} onChange={(e) => setRegion(e.target.value)} className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-1.5 text-sm" />
        </div>
        <div>
          <label className="text-xs text-[var(--ink-soft)]">General rate — male (GH₵)</label>
          <input type="number" min="0" step="0.01" value={maleRate} onChange={(e) => setMaleRate(e.target.value)} className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-1.5 text-sm" />
        </div>
        <div>
          <label className="text-xs text-[var(--ink-soft)]">General rate — female (GH₵)</label>
          <input type="number" min="0" step="0.01" value={femaleRate} onChange={(e) => setFemaleRate(e.target.value)} className="mt-1 w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-1.5 text-sm" />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button onClick={() => update.mutate()} disabled={update.isPending} className="rounded-sm bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60">
          Save changes
        </button>
        {community.is_active ? (
          <button onClick={() => deactivate.mutate()} className="rounded-sm border border-[var(--rule)] px-3 py-1.5 text-xs font-medium hover:border-[var(--clay-red)] hover:text-[var(--clay-red)]">
            Deactivate
          </button>
        ) : (
          <button onClick={() => reactivate.mutate()} className="rounded-sm border border-[var(--rule)] px-3 py-1.5 text-xs font-medium hover:border-[var(--forest)] hover:text-[var(--forest)]">
            Reactivate
          </button>
        )}
        <button onClick={() => remove.mutate()} className="rounded-sm px-3 py-1.5 text-xs font-medium text-[var(--clay-red)]">
          Delete permanently
        </button>
      </div>
      {deleteError && <p className="text-xs text-[var(--clay-red)]">{deleteError}</p>}

      <div className="border-t border-[var(--rule)] pt-3">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Access period</p>
        <p className="mt-1 text-sm">
          {community.access_expires_at ? (
            <>
              {community.access_plan === "single_funeral" ? "Single-funeral" : "Time-limited"} access —{" "}
              {community.is_access_expired ? (
                <span className="text-[var(--clay-red)]">expired</span>
              ) : (
                <span>{community.access_days_remaining} day{community.access_days_remaining === 1 ? "" : "s"} remaining</span>
              )}
            </>
          ) : (
            "Ongoing (permanent) access"
          )}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <input
            type="number" min="1" value={extendDays} onChange={(e) => setExtendDays(e.target.value)}
            className="w-20 rounded-sm border border-[var(--rule)] bg-white px-2 py-1.5 text-xs"
          />
          <button
            onClick={() => extendAccess.mutate()}
            disabled={extendAccess.isPending || !extendDays}
            className="rounded-sm border border-[var(--rule)] px-3 py-1.5 text-xs font-medium hover:border-[var(--forest)] hover:text-[var(--forest)] disabled:opacity-60"
          >
            + Add days
          </button>
          {community.access_expires_at && (
            <button
              onClick={() => makePermanent.mutate()}
              disabled={makePermanent.isPending}
              className="rounded-sm border border-[var(--rule)] px-3 py-1.5 text-xs font-medium hover:border-[var(--forest)] hover:text-[var(--forest)]"
            >
              Make permanent
            </button>
          )}
          {community.access_expires_at && !community.is_access_expired && (
            <button
              onClick={() => { if (window.confirm(`End '${community.name}'s access right now, before its scheduled expiry? This can't be undone.`)) terminateAccess.mutate(); }}
              disabled={terminateAccess.isPending}
              className="rounded-sm border border-[var(--rule)] px-3 py-1.5 text-xs font-medium text-[var(--clay-red)] hover:border-[var(--clay-red)]"
            >
              Terminate license now
            </button>
          )}
        </div>
      </div>

      <PayoutAccountsPanel communityId={community.id} />
      <BillingRecordsPanel communityId={community.id} />

      <div className="border-t border-[var(--rule)] pt-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Community Admins</p>
          <button onClick={() => setShowAddAdmin(true)} className="text-xs text-[var(--forest)] hover:underline">+ Add admin</button>
        </div>
        <ul className="mt-2 flex flex-wrap gap-2">
          {admins?.map((a) => (
            <AdminBadge key={a.id} username={a.username} />
          ))}
        </ul>
        {showAddAdmin && (
          <AddAdminForm
            communityId={community.id}
            onDone={() => { setShowAddAdmin(false); qc.invalidateQueries({ queryKey: ["community-admins", community.id] }); }}
          />
        )}
      </div>
    </div>
  );
}

function AdminBadge({ username }: { username: string }) {
  const [resetting, setResetting] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const resetPassword = useMutation({
    mutationFn: (newPassword: string) => tenantsApi.resetAdministratorPassword({ username, new_password: newPassword }),
    onSuccess: () => setResult("Password reset."),
    onError: (err: Error) => setResult(err.message),
  });

  return (
    <li className="rounded-full bg-white px-3 py-1 text-xs font-medium">
      {username}
      <button
        onClick={() => setResetting((s) => !s)}
        className="ml-2 text-[var(--ink-soft)] hover:text-[var(--forest)] hover:underline"
        title="Reset administrator accounts when requested"
      >
        reset password
      </button>
      {resetting && (
        <span className="ml-2 inline-flex items-center gap-1">
          <input
            type="password"
            placeholder="New password"
            className="w-28 rounded-sm border border-[var(--rule)] px-2 py-0.5 text-xs"
            onKeyDown={(e) => {
              if (e.key === "Enter" && e.currentTarget.value.length >= 8) {
                resetPassword.mutate(e.currentTarget.value);
                setResetting(false);
              }
            }}
          />
        </span>
      )}
      {result && <span className="ml-2 text-[var(--ink-soft)]">{result}</span>}
    </li>
  );
}

function AddAdminForm({ communityId, onDone }: { communityId: string; onDone: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const add = useMutation({
    mutationFn: () => tenantsApi.addAdmin(communityId, { username, password }),
    onSuccess: onDone,
    onError: (err: Error) => setError(err.message),
  });

  return (
    <form onSubmit={(e) => { e.preventDefault(); add.mutate(); }} className="mt-2 flex items-end gap-2">
      <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username" className="rounded-sm border border-[var(--rule)] bg-white px-2 py-1 text-xs" />
      <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password (8+ chars)" className="rounded-sm border border-[var(--rule)] bg-white px-2 py-1 text-xs" />
      <button type="submit" disabled={add.isPending} className="rounded-sm bg-[var(--forest)] px-2 py-1 text-xs font-medium text-white">Add</button>
      {error && <span className="text-xs text-[var(--clay-red)]">{error}</span>}
    </form>
  );
}

function AnnouncementReviewSection() {
  const qc = useQueryClient();
  const [rejectDrafts, setRejectDrafts] = useState<Record<string, string>>({});
  const [homepageDecisions, setHomepageDecisions] = useState<Record<string, boolean>>({});
  const { data: pending } = useQuery({ queryKey: ["announcements-pending-review"], queryFn: announcementsApi.listPendingReview });

  const approve = useMutation({
    mutationFn: (id: string) => announcementsApi.approve(id, { feature_on_homepage: homepageDecisions[id] }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["announcements-pending-review"] });
      qc.invalidateQueries({ queryKey: ["notice-board"] });
      qc.invalidateQueries({ queryKey: ["homepage-featured-announcements"] });
    },
  });
  const reject = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) => announcementsApi.reject(id, reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["announcements-pending-review"] }),
  });

  return (
    <section className="rounded-sm border border-[var(--rule)] bg-white p-6">
      <h2 className="font-display text-xl">Announcements awaiting review</h2>
      <p className="mt-1 text-sm text-[var(--ink-soft)]">
        Approve as submitted, or reject with a reason — the community admin will see it and can
        edit and resend. If a community requested homepage placement, you decide whether to
        actually grant it.
      </p>

      {pending?.length === 0 && <p className="mt-3 text-sm text-[var(--ink-soft)]">Nothing waiting right now.</p>}
      <div className="mt-3 space-y-3">
        {pending?.map((a) => (
          <div key={a.id} className="rounded-sm bg-[var(--surface)] p-4">
            <div className="flex items-center justify-between">
              <p className="font-mono text-xs uppercase tracking-wide text-[var(--ink-soft)]">{a.community_name}</p>
              {a.homepage_feature_requested && (
                <span className="rounded-full bg-[var(--gold-soft)] px-2 py-0.5 text-xs font-medium" style={{ color: "var(--gold)" }}>
                  Requested for homepage
                </span>
              )}
            </div>
            <p className="mt-1 font-medium">{a.title}</p>
            <p className="mt-1 text-sm">{a.content}</p>
            {a.image_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={a.image_url} alt="" className="mt-2 max-h-40 rounded-sm object-cover" />
            )}
            {a.homepage_feature_requested && (
              <label className="mt-2 flex items-center gap-2 text-xs text-[var(--ink-soft)]">
                <input
                  type="checkbox"
                  defaultChecked
                  onChange={(e) => setHomepageDecisions((d) => ({ ...d, [a.id]: e.target.checked }))}
                />
                Grant homepage placement (your decision, independent of approving this for the Notice Board)
              </label>
            )}
            <div className="mt-3 flex items-center gap-2">
              <button onClick={() => approve.mutate(a.id)} className="rounded-sm bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white">
                Approve
              </button>
              <input
                placeholder="Reason if rejecting"
                onChange={(e) => setRejectDrafts((d) => ({ ...d, [a.id]: e.target.value }))}
                className="flex-1 rounded-sm border border-[var(--rule)] px-2 py-1.5 text-xs"
              />
              <button
                onClick={() => rejectDrafts[a.id]?.trim() && reject.mutate({ id: a.id, reason: rejectDrafts[a.id] })}
                disabled={!rejectDrafts[a.id]?.trim()}
                className="rounded-sm border border-[var(--clay-red)] px-3 py-1.5 text-xs font-medium text-[var(--clay-red)] disabled:opacity-50"
              >
                Reject
              </button>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function PlanInterestSection() {
  const qc = useQueryClient();
  const { data: submissions } = useQuery({ queryKey: ["plan-interest"], queryFn: planInterestApi.listAll });
  const markContacted = useMutation({
    mutationFn: (id: string) => planInterestApi.markContacted(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["plan-interest"] }),
  });

  const pending = submissions?.filter((s) => !s.contacted) ?? [];
  const contacted = submissions?.filter((s) => s.contacted) ?? [];

  return (
    <section className="rounded-sm border border-[var(--rule)] bg-white p-6">
      <h2 className="font-display text-xl">Plan interest</h2>
      <p className="mt-1 text-sm text-[var(--ink-soft)]">
        Everyone who registered interest in a not-yet-available pricing plan from the
        homepage — real leads to follow up with.
      </p>

      {pending.length === 0 ? (
        <p className="mt-3 text-sm text-[var(--ink-soft)]">Nothing new right now.</p>
      ) : (
        <ul className="mt-3 divide-y divide-[var(--rule)]">
          {pending.map((s) => (
            <li key={s.id} className="flex items-center justify-between py-2 text-sm">
              <span>
                <strong>{s.name}</strong> — {s.plan_type.replace(/_/g, " ")} — {s.email || s.phone}
              </span>
              <button onClick={() => markContacted.mutate(s.id)} className="text-xs text-[var(--forest)] hover:underline">
                Mark contacted
              </button>
            </li>
          ))}
        </ul>
      )}
      {contacted.length > 0 && (
        <p className="mt-3 text-xs text-[var(--ink-soft)]">{contacted.length} already contacted.</p>
      )}
    </section>
  );
}

function HomepageImagesSection() {
  const qc = useQueryClient();
  const [caption, setCaption] = useState("");
  const [subcaption, setSubcaption] = useState("");
  const [file, setFile] = useState<File | null>(null);

  const { data: images } = useQuery({ queryKey: ["homepage-images-manage"], queryFn: homepageImagesApi.listAll });
  const upload = useMutation({
    mutationFn: () => homepageImagesApi.upload({ image: file!, caption, subcaption }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["homepage-images-manage"] }); qc.invalidateQueries({ queryKey: ["homepage-images-public"] }); setFile(null); setCaption(""); setSubcaption(""); },
  });
  const deactivate = useMutation({
    mutationFn: (id: string) => homepageImagesApi.deactivate(id),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["homepage-images-manage"] }); qc.invalidateQueries({ queryKey: ["homepage-images-public"] }); },
  });

  return (
    <section className="rounded-sm border border-[var(--rule)] bg-white p-6">
      <h2 className="font-display text-xl">Homepage images</h2>
      <p className="mt-1 text-sm text-[var(--ink-soft)]">
        The rotating photo on the public homepage&apos;s hero — upload as many as you like; they
        rotate automatically for every visitor.
      </p>

      <form
        onSubmit={(e) => { e.preventDefault(); if (file) upload.mutate(); }}
        className="mt-4 flex flex-wrap items-end gap-2 rounded-sm bg-[var(--surface)] p-3"
      >
        <input type="file" accept="image/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="text-sm" />
        <input value={caption} onChange={(e) => setCaption(e.target.value)} placeholder="Caption (optional)" className="rounded-sm border border-[var(--rule)] bg-white px-2 py-1.5 text-sm" />
        <input value={subcaption} onChange={(e) => setSubcaption(e.target.value)} placeholder="Subcaption (optional)" className="rounded-sm border border-[var(--rule)] bg-white px-2 py-1.5 text-sm" />
        <button type="submit" disabled={!file || upload.isPending} className="rounded-sm bg-[var(--forest)] px-3 py-1.5 text-sm font-medium text-white disabled:opacity-60">
          {upload.isPending ? "Uploading…" : "Upload"}
        </button>
      </form>
      {upload.isError && <p className="mt-2 text-sm text-[var(--clay-red)]">{(upload.error as Error).message}</p>}

      <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {images?.map((img) => (
          <div key={img.id} className="overflow-hidden rounded-sm border border-[var(--rule)]">
            {img.image_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={img.image_url} alt={img.caption} className="h-24 w-full object-cover" />
            )}
            <div className="p-1.5 text-xs">
              <p className="truncate">{img.caption || "—"}</p>
              {img.is_active ? (
                <button onClick={() => deactivate.mutate(img.id)} className="text-[var(--clay-red)] hover:underline">Remove</button>
              ) : (
                <span className="text-[var(--ink-soft)]">removed</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function PayoutAccountsPanel({ communityId }: { communityId: string }) {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [accountType, setAccountType] = useState<"mobile_money" | "bank">("mobile_money");
  const [provider, setProvider] = useState("");
  const [number, setNumber] = useState("");
  const [holder, setHolder] = useState("");

  const { data: accounts } = useQuery({ queryKey: ["payout-accounts", communityId], queryFn: () => tenantsApi.listPayoutAccounts(communityId) });
  const add = useMutation({
    mutationFn: () => tenantsApi.addPayoutAccount(communityId, { account_type: accountType, provider_name: provider, account_number: number, account_holder_name: holder }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["payout-accounts", communityId] }); setShowAdd(false); setProvider(""); setNumber(""); setHolder(""); },
  });
  const deactivate = useMutation({
    mutationFn: (accountId: string) => tenantsApi.deactivatePayoutAccount(communityId, accountId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["payout-accounts", communityId] }),
  });

  return (
    <div className="border-t border-[var(--rule)] pt-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">
          Payout accounts — where this community&apos;s electronic contributions go
        </p>
        <button onClick={() => setShowAdd((v) => !v)} className="text-xs text-[var(--forest)] hover:underline">+ Add account</button>
      </div>

      {accounts && accounts.length === 0 && !showAdd && (
        <p className="mt-1 text-xs text-[var(--ink-soft)]">No payout account configured yet.</p>
      )}
      {accounts?.map((a) => (
        <div key={a.id} className="mt-2 flex items-center justify-between rounded-sm bg-white p-2 text-xs">
          <span>
            {a.provider_name} — {a.account_number} ({a.account_holder_name})
            {!a.is_active && <span className="ml-1 text-[var(--ink-soft)]">(inactive)</span>}
          </span>
          {a.is_active && (
            <button onClick={() => deactivate.mutate(a.id)} className="text-[var(--clay-red)] hover:underline">Deactivate</button>
          )}
        </div>
      ))}

      {showAdd && (
        <form onSubmit={(e) => { e.preventDefault(); add.mutate(); }} className="mt-2 space-y-2 rounded-sm bg-white p-2">
          <select value={accountType} onChange={(e) => setAccountType(e.target.value as typeof accountType)} className="w-full rounded-sm border border-[var(--rule)] px-2 py-1 text-xs">
            <option value="mobile_money">Mobile Money</option>
            <option value="bank">Bank Account</option>
          </select>
          <input value={provider} onChange={(e) => setProvider(e.target.value)} placeholder="Provider (e.g. MTN Mobile Money)" className="w-full rounded-sm border border-[var(--rule)] px-2 py-1 text-xs" />
          <input value={number} onChange={(e) => setNumber(e.target.value)} placeholder="Account / phone number" className="w-full rounded-sm border border-[var(--rule)] px-2 py-1 text-xs" />
          <input value={holder} onChange={(e) => setHolder(e.target.value)} placeholder="Account holder name" className="w-full rounded-sm border border-[var(--rule)] px-2 py-1 text-xs" />
          {add.isError && <p className="text-xs text-[var(--clay-red)]">{(add.error as Error).message}</p>}
          <button type="submit" disabled={add.isPending} className="rounded-sm bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60">
            {add.isPending ? "Saving…" : "Save account"}
          </button>
        </form>
      )}
    </div>
  );
}

function BillingRecordsPanel({ communityId }: { communityId: string }) {
  const qc = useQueryClient();
  const [showAdd, setShowAdd] = useState(false);
  const [description, setDescription] = useState("");
  const [amount, setAmount] = useState("");

  const { data: records } = useQuery({ queryKey: ["billing-records", communityId], queryFn: () => tenantsApi.listBillingRecords(communityId) });
  const create = useMutation({
    mutationFn: () => tenantsApi.createBillingRecord(communityId, { description, amount }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["billing-records", communityId] }); setShowAdd(false); setDescription(""); setAmount(""); },
  });
  const markPaid = useMutation({
    mutationFn: (recordId: string) => tenantsApi.markBillingRecordPaid(communityId, recordId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["billing-records", communityId] }),
  });
  const waive = useMutation({
    mutationFn: (recordId: string) => tenantsApi.waiveBillingRecord(communityId, recordId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["billing-records", communityId] }),
  });

  return (
    <div className="border-t border-[var(--rule)] pt-3">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">
          Platform billing — what this community owes Nsaabodeɛ Smart itself
        </p>
        <button onClick={() => setShowAdd((v) => !v)} className="text-xs text-[var(--forest)] hover:underline">+ Add charge</button>
      </div>
      <p className="mt-1 text-xs text-[var(--ink-soft)]">
        Entirely separate from this community&apos;s own funeral contributions — never mixed with, or deducted from, the community&apos;s own funds.
      </p>

      {records?.map((r) => (
        <div key={r.id} className="mt-2 rounded-sm bg-white p-2 text-xs">
          <div className="flex items-center justify-between">
            <span>{r.description} — GHS {r.amount}</span>
            <span className={r.status === "paid" ? "font-medium" : r.status === "waived" ? "text-[var(--ink-soft)]" : "font-medium text-[var(--gold)]"} style={r.status === "paid" ? { color: "var(--forest)" } : undefined}>
              {r.status}
            </span>
          </div>
          {r.status === "unpaid" && (
            <div className="mt-1 flex gap-2">
              <button onClick={() => markPaid.mutate(r.id)} className="text-[var(--forest)] hover:underline">Mark paid</button>
              <button onClick={() => waive.mutate(r.id)} className="text-[var(--ink-soft)] hover:underline">Waive</button>
            </div>
          )}
        </div>
      ))}

      {showAdd && (
        <form onSubmit={(e) => { e.preventDefault(); create.mutate(); }} className="mt-2 space-y-2 rounded-sm bg-white p-2">
          <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description (e.g. Monthly subscription — July 2026)" className="w-full rounded-sm border border-[var(--rule)] px-2 py-1 text-xs" />
          <input value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Amount (GHS)" className="w-full rounded-sm border border-[var(--rule)] px-2 py-1 text-xs" />
          {create.isError && <p className="text-xs text-[var(--clay-red)]">{(create.error as Error).message}</p>}
          <button type="submit" disabled={create.isPending} className="rounded-sm bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60">
            {create.isPending ? "Saving…" : "Add charge"}
          </button>
        </form>
      )}
    </div>
  );
}

function CreateCommunityDialog({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [communityName, setCommunityName] = useState("");
  const [region, setRegion] = useState("");
  const [adminUsername, setAdminUsername] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [accessType, setAccessType] = useState<"ongoing" | "single_funeral" | "time_limited">("ongoing");
  const [accessDays, setAccessDays] = useState("7");
  const [payoutType, setPayoutType] = useState<"mobile_money" | "bank">("mobile_money");
  const [payoutProvider, setPayoutProvider] = useState("");
  const [payoutNumber, setPayoutNumber] = useState("");
  const [payoutHolder, setPayoutHolder] = useState("");

  const create = useMutation({
    mutationFn: () => tenantsApi.create({
      community_name: communityName, region, admin_username: adminUsername, admin_password: adminPassword,
      ...(accessType !== "ongoing" ? {
        access_days: Number(accessDays), access_plan: accessType,
        payout_account_type: payoutType, payout_provider_name: payoutProvider,
        payout_account_number: payoutNumber, payout_account_holder_name: payoutHolder,
      } : {}),
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["communities"] }); onClose(); },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-sm bg-[var(--surface)] p-6 text-[var(--ink)]">
        <h2 className="font-display text-xl">New community</h2>
        <form onSubmit={(e) => { e.preventDefault(); create.mutate(); }} className="mt-4 space-y-3">
          <input value={communityName} onChange={(e) => setCommunityName(e.target.value)} placeholder="Community name" className="w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm" />
          <input value={region} onChange={(e) => setRegion(e.target.value)} placeholder="Region (optional)" className="w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm" />
          <input value={adminUsername} onChange={(e) => setAdminUsername(e.target.value)} placeholder="First admin's username" className="w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm" />
          <input type="password" value={adminPassword} onChange={(e) => setAdminPassword(e.target.value)} placeholder="Password (8+ chars)" className="w-full rounded-sm border border-[var(--rule)] bg-white px-3 py-2 text-sm" />

          <div className="rounded-sm bg-white p-3">
            <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Access</p>
            <select value={accessType} onChange={(e) => setAccessType(e.target.value as typeof accessType)} className="mt-2 w-full rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm">
              <option value="ongoing">Ongoing (permanent)</option>
              <option value="single_funeral">Single funeral (temporary)</option>
              <option value="time_limited">Time-limited (temporary)</option>
            </select>
            {accessType !== "ongoing" && (
              <>
                <div className="mt-2 flex items-center gap-2">
                  <input type="number" min="1" value={accessDays} onChange={(e) => setAccessDays(e.target.value)} className="w-20 rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm" />
                  <span className="text-xs text-[var(--ink-soft)]">days from now</span>
                </div>
                <div className="mt-3 border-t border-[var(--rule)] pt-3">
                  <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">
                    Payout account (required) — where donations for the bereaved family go
                  </p>
                  <select value={payoutType} onChange={(e) => setPayoutType(e.target.value as typeof payoutType)} className="mt-2 w-full rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm">
                    <option value="mobile_money">Mobile Money</option>
                    <option value="bank">Bank Account</option>
                  </select>
                  <input value={payoutProvider} onChange={(e) => setPayoutProvider(e.target.value)} placeholder="Provider (e.g. MTN Mobile Money)" className="mt-2 w-full rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm" />
                  <input value={payoutNumber} onChange={(e) => setPayoutNumber(e.target.value)} placeholder="Account / phone number" className="mt-2 w-full rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm" />
                  <input value={payoutHolder} onChange={(e) => setPayoutHolder(e.target.value)} placeholder="Account holder name" className="mt-2 w-full rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm" />
                </div>
              </>
            )}
          </div>

          {create.isError && <p className="text-sm text-[var(--clay-red)]">{(create.error as Error).message}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-3 py-2 text-sm text-[var(--ink-soft)]">Cancel</button>
            <button type="submit" disabled={create.isPending} className="rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
              {create.isPending ? "Creating…" : "Create community"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
