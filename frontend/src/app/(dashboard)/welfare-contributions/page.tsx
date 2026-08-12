"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useContributionCategories, useCampaigns, useCampaignObligations, useWelfareActions } from "@/lib/hooks/useWelfare";
import { familiesApi } from "@/lib/api/families";
import { formatCedis } from "@/lib/formatCedis";
import { useAuthStore } from "@/store/authStore";
import type { ContributionAmountType, ContributionFrequency, ContributionCampaign } from "@/lib/api/welfare";

const FREQUENCY_LABEL: Record<ContributionFrequency, string> = {
  one_time: "One-Time", monthly: "Monthly", quarterly: "Quarterly", annual: "Annual",
};
const STATUS_ACCENT: Record<string, string> = {
  pending_approval: "var(--gold)", family_approved: "var(--violet)", active: "var(--forest)", rejected: "var(--clay-red)", closed: "var(--ink-soft)",
};

const CAN_CREATE_CATEGORY = ["community_admin"];
const CAN_START_COMMUNITY_CAMPAIGN = ["community_admin", "chairman", "secretary"];

/**
 * 'Nsaabodeɛ Smart must not be limited to funeral contributions...
 * every community should also be able to use the platform for general
 * welfare and community development contributions.' Monthly welfare,
 * annual dues, development levies, emergency fundraising, scholarship
 * and health support funds, and any other community-defined type —
 * every one of them its own genuinely separate ledger, never mixed
 * with funeral contributions or gift donations.
 */
export default function WelfareContributionsPage() {
  const user = useAuthStore((s) => s.user);
  const canCreateCategory = !!user?.role && CAN_CREATE_CATEGORY.includes(user.role);
  const canStartCommunityWide = !!user?.role && CAN_START_COMMUNITY_CAMPAIGN.includes(user.role);
  const isFamilyHead = user?.role === "family_head";

  const { data: categories } = useContributionCategories();
  const { data: campaigns } = useCampaigns();
  const { createCategory, initiateCommunityCampaign, initiateFamilyCampaign, decideCampaign, adminApproveCampaign } = useWelfareActions();

  const [showNewCategory, setShowNewCategory] = useState(false);
  const [showNewCampaign, setShowNewCampaign] = useState(false);
  const [selectedCampaign, setSelectedCampaign] = useState<ContributionCampaign | null>(null);

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Beyond Funerals</p>
        <div className="mt-1 flex items-start justify-between gap-4">
          <div>
            <h1 className="font-display text-4xl">Welfare & Community Contributions</h1>
            <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
              Monthly welfare, annual dues, development levies, emergency fundraising, scholarships,
              health support, and any other purpose your community defines — each its own
              separate ledger, never mixed with funeral contributions or gift donations.
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            {canCreateCategory && (
              <button onClick={() => setShowNewCategory(true)} className="bg-[var(--violet)] px-4 py-2 text-sm font-medium text-white">
                New category
              </button>
            )}
            {(canStartCommunityWide || isFamilyHead) && (
              <button onClick={() => setShowNewCampaign(true)} className="bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white">
                Start a campaign
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="grid gap-6 px-8 py-8 lg:grid-cols-2">
        <section className="rounded-sm border border-[var(--rule)] bg-white p-5">
          <h2 className="font-display text-xl">Contribution Categories</h2>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">The reusable types a campaign is started under.</p>
          <ul className="mt-4 divide-y divide-[var(--rule)]">
            {categories?.map((c) => (
              <li key={c.id} className="py-3">
                <div className="flex items-center justify-between">
                  <p className="font-medium">{c.name}</p>
                  <span className="font-mono text-xs text-[var(--ink-soft)]">{FREQUENCY_LABEL[c.frequency]}</span>
                </div>
                <p className="mt-0.5 text-xs text-[var(--ink-soft)]">
                  {c.is_mandatory ? "Mandatory" : "Optional"} · {c.amount_type === "fixed" ? formatCedis(c.fixed_amount ?? "0") : "Flexible amount"}
                  {" · "}{c.required_family_approvals} approval(s) if family-initiated
                </p>
                {c.purpose && <p className="mt-1 text-xs italic text-[var(--ink-soft)]">{c.purpose}</p>}
              </li>
            ))}
            {categories?.length === 0 && <p className="py-4 text-sm text-[var(--ink-soft)]">No categories yet.</p>}
          </ul>
        </section>

        <section className="rounded-sm border border-[var(--rule)] bg-white p-5">
          <h2 className="font-display text-xl">Campaigns</h2>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">Community-wide, plus your own family&apos;s.</p>
          <ul className="mt-4 divide-y divide-[var(--rule)]">
            {campaigns?.map((c) => (
              <li key={c.id} className="py-3">
                <div className="flex items-center justify-between gap-2">
                  <button onClick={() => setSelectedCampaign(c)} className="text-left font-medium hover:text-[var(--forest)] hover:underline">
                    {c.title}
                  </button>
                  <span className="font-mono text-[10px] font-medium uppercase tracking-wide" style={{ color: STATUS_ACCENT[c.status] }}>
                    {c.status.replace(/_/g, " ")}
                  </span>
                </div>
                <p className="mt-0.5 text-xs text-[var(--ink-soft)]">
                  {c.category_name} · {c.family_name ?? "Community-wide"} · {formatCedis(c.amount)}
                </p>
                {c.status === "pending_approval" && c.family && (
                  <div className="mt-2 flex gap-2">
                    <button onClick={() => decideCampaign.mutate({ campaignId: c.id, approve: true })} className="rounded-sm border border-[var(--forest)] px-2 py-1 text-xs text-[var(--forest)]">
                      Approve
                    </button>
                    <button onClick={() => decideCampaign.mutate({ campaignId: c.id, approve: false })} className="rounded-sm border border-[var(--clay-red)] px-2 py-1 text-xs text-[var(--clay-red)]">
                      Reject
                    </button>
                  </div>
                )}
                {c.status === "family_approved" && user?.role === "community_admin" && (
                  <div className="mt-2 flex gap-2">
                    <button onClick={() => adminApproveCampaign.mutate({ campaignId: c.id, approve: true })} className="rounded-sm border border-[var(--gold)] px-2 py-1 text-xs text-[var(--gold)]">
                      Give final approval — bill {c.family_name}&apos;s members
                    </button>
                    <button onClick={() => adminApproveCampaign.mutate({ campaignId: c.id, approve: false })} className="rounded-sm border border-[var(--clay-red)] px-2 py-1 text-xs text-[var(--clay-red)]">
                      Reject
                    </button>
                  </div>
                )}
              </li>
            ))}
            {campaigns?.length === 0 && <p className="py-4 text-sm text-[var(--ink-soft)]">No campaigns yet.</p>}
          </ul>
        </section>
      </main>

      {showNewCategory && <NewCategoryDialog onClose={() => setShowNewCategory(false)} onCreate={createCategory} />}
      {showNewCampaign && (
        <NewCampaignDialog
          categories={categories ?? []}
          canStartCommunityWide={canStartCommunityWide}
          isFamilyHead={isFamilyHead}
          onClose={() => setShowNewCampaign(false)}
          onInitiateCommunity={initiateCommunityCampaign}
          onInitiateFamily={initiateFamilyCampaign}
        />
      )}
      {selectedCampaign && <CampaignObligationsDialog campaign={selectedCampaign} onClose={() => setSelectedCampaign(null)} />}
    </div>
  );
}

function NewCategoryDialog({ onClose, onCreate }: { onClose: () => void; onCreate: ReturnType<typeof useWelfareActions>["createCategory"] }) {
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState("");
  const [amountType, setAmountType] = useState<ContributionAmountType>("fixed");
  const [fixedAmount, setFixedAmount] = useState("");
  const [frequency, setFrequency] = useState<ContributionFrequency>("one_time");
  const [isMandatory, setIsMandatory] = useState(true);
  const [requiredApprovals, setRequiredApprovals] = useState("2");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    onCreate.mutate(
      {
        name, purpose, amount_type: amountType, fixed_amount: amountType === "fixed" ? fixedAmount : undefined,
        frequency, is_mandatory: isMandatory, required_family_approvals: Number(requiredApprovals),
      },
      { onSuccess: onClose }
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <form onSubmit={submit} className="w-full max-w-md space-y-3 rounded-sm bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-xl">New contribution category</h2>
          <button type="button" onClick={onClose} className="text-[var(--ink-soft)]">✕</button>
        </div>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name, e.g. Monthly Welfare Contribution"
          className="w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm" />
        <textarea value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder="Purpose (optional)" rows={2}
          className="w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm" />
        <div className="flex gap-3">
          <select value={amountType} onChange={(e) => setAmountType(e.target.value as ContributionAmountType)} className="flex-1 rounded-sm border border-[var(--rule)] px-3 py-2 text-sm">
            <option value="fixed">Fixed amount</option>
            <option value="flexible">Flexible amount</option>
          </select>
          {amountType === "fixed" && (
            <input type="number" min="0.01" step="0.01" value={fixedAmount} onChange={(e) => setFixedAmount(e.target.value)} placeholder="Amount"
              className="flex-1 rounded-sm border border-[var(--rule)] px-3 py-2 text-sm" />
          )}
        </div>
        <select value={frequency} onChange={(e) => setFrequency(e.target.value as ContributionFrequency)} className="w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm">
          {Object.entries(FREQUENCY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={isMandatory} onChange={(e) => setIsMandatory(e.target.checked)} /> Mandatory
        </label>
        <div>
          <label className="text-xs font-medium">Required family approvals (if a family initiates it)</label>
          <input type="number" min="1" max="10" value={requiredApprovals} onChange={(e) => setRequiredApprovals(e.target.value)}
            className="mt-1 w-24 rounded-sm border border-[var(--rule)] px-3 py-2 text-sm" />
        </div>
        {onCreate.isError && <p className="text-sm text-[var(--clay-red)]">{onCreate.error.message}</p>}
        <button type="submit" disabled={onCreate.isPending || !name.trim()} className="w-full rounded-sm bg-[var(--violet)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
          {onCreate.isPending ? "Creating…" : "Create category"}
        </button>
      </form>
    </div>
  );
}

function NewCampaignDialog({
  categories, canStartCommunityWide, isFamilyHead, onClose, onInitiateCommunity, onInitiateFamily,
}: {
  categories: { id: string; name: string; amount_type: ContributionAmountType }[];
  canStartCommunityWide: boolean;
  isFamilyHead: boolean;
  onClose: () => void;
  onInitiateCommunity: ReturnType<typeof useWelfareActions>["initiateCommunityCampaign"];
  onInitiateFamily: ReturnType<typeof useWelfareActions>["initiateFamilyCampaign"];
}) {
  const [scope, setScope] = useState<"community" | "family">(canStartCommunityWide ? "community" : "family");
  const [categoryId, setCategoryId] = useState("");
  const [title, setTitle] = useState("");
  const [amount, setAmount] = useState("");
  const [familyId, setFamilyId] = useState("");
  const { data: families } = useQuery({ queryKey: ["families-for-welfare"], queryFn: () => familiesApi.list() });
  const selectedCategory = categories.find((c) => c.id === categoryId);
  const mutation = scope === "community" ? onInitiateCommunity : onInitiateFamily;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const input = { category_id: categoryId, title, amount: selectedCategory?.amount_type === "flexible" ? amount : undefined };
    if (scope === "community") {
      onInitiateCommunity.mutate(input, { onSuccess: onClose });
    } else {
      onInitiateFamily.mutate({ familyId, input }, { onSuccess: onClose });
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <form onSubmit={submit} className="w-full max-w-md space-y-3 rounded-sm bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-xl">Start a contribution campaign</h2>
          <button type="button" onClick={onClose} className="text-[var(--ink-soft)]">✕</button>
        </div>

        {canStartCommunityWide && isFamilyHead && (
          <div className="flex gap-1 rounded-full bg-[var(--surface)] p-1 text-xs">
            {(["community", "family"] as const).map((s) => (
              <button key={s} type="button" onClick={() => setScope(s)}
                className={`flex-1 rounded-full px-3 py-1.5 font-medium ${scope === s ? "bg-[var(--ink)] text-white" : "text-[var(--ink-soft)]"}`}>
                {s === "community" ? "Community-wide" : "My family only"}
              </button>
            ))}
          </div>
        )}
        {scope === "family" && (
          <p className="text-xs text-[var(--ink-soft)]">
            This will need approval from two of your family&apos;s other executives before members are billed.
          </p>
        )}

        <select value={categoryId} onChange={(e) => setCategoryId(e.target.value)} className="w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm">
          <option value="">Select a category…</option>
          {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>

        {scope === "family" && (
          <select value={familyId} onChange={(e) => setFamilyId(e.target.value)} className="w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm">
            <option value="">Select your family…</option>
            {families?.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
        )}

        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title, e.g. July 2026 Welfare Contribution"
          className="w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm" />

        {selectedCategory?.amount_type === "flexible" && (
          <input type="number" min="0.01" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="Amount"
            className="w-full rounded-sm border border-[var(--rule)] px-3 py-2 text-sm" />
        )}

        {mutation.isError && <p className="text-sm text-[var(--clay-red)]">{mutation.error.message}</p>}
        <button type="submit" disabled={mutation.isPending || !categoryId || !title.trim() || (scope === "family" && !familyId)}
          className="w-full rounded-sm bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
          {mutation.isPending ? "Starting…" : "Start campaign"}
        </button>
      </form>
    </div>
  );
}

function CampaignObligationsDialog({ campaign, onClose }: { campaign: ContributionCampaign; onClose: () => void }) {
  const { data: obligations, isLoading } = useCampaignObligations(campaign.id);
  const { recordPayment } = useWelfareActions();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-sm bg-white p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-xl">{campaign.title}</h2>
          <button onClick={onClose} className="text-[var(--ink-soft)]">✕</button>
        </div>
        <p className="mt-1 text-xs text-[var(--ink-soft)]">{campaign.category_name} · {campaign.family_name ?? "Community-wide"}</p>

        {isLoading && <p className="mt-4 text-sm text-[var(--ink-soft)]">Loading…</p>}
        {campaign.status !== "active" && (
          <p className="mt-4 text-sm text-[var(--ink-soft)]">No members are billed until this campaign is active.</p>
        )}

        <ul className="mt-4 divide-y divide-[var(--rule)]">
          {obligations?.map((o) => (
            <li key={o.id} className="flex items-center justify-between gap-2 py-2">
              <div>
                <p className="text-sm">{o.member_name}</p>
                <p className="text-xs text-[var(--ink-soft)]">{o.payment_status} · owes {formatCedis(o.balance)}</p>
              </div>
              {o.payment_status !== "paid" && (
                <button
                  onClick={() => {
                    const amt = window.prompt(`Amount to record for ${o.member_name} (owes ${o.balance})?`, o.balance);
                    if (amt) recordPayment.mutate({ obligationId: o.id, input: { amount: amt, method: "cash" }, campaignId: campaign.id });
                  }}
                  className="shrink-0 rounded-sm border border-[var(--forest)] px-2 py-1 text-xs text-[var(--forest)]"
                >
                  Record payment
                </button>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
