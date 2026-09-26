"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { tenantsApi, type SubscriptionPlan, type SubscriptionPlanInput } from "@/lib/api/tenants";
import { formatCedis } from "@/lib/formatCedis";
import { Field, FormSection, FIELD_INPUT_CLASS } from "@/components/forms/FormPrimitives";

/**
 * "This is how I want the subscription plan to be." Plans as real,
 * editable records: one card each with name, description, yearly and
 * monthly price, member limit, trial length, how many communities are
 * on it, and a feature checklist — plus "+ New plan" and "Edit", so
 * Platform Admin is never stuck with a fixed set.
 */
export default function PlansPage() {
  const { data: plans, isLoading, error } = useQuery({ queryKey: ["subscription-plans"], queryFn: tenantsApi.listSubscriptionPlans });
  const [editing, setEditing] = useState<SubscriptionPlan | "new" | null>(null);

  return (
    <div className="font-body min-h-screen bg-[var(--bg)] text-[var(--text)]">
      <header className="border-b border-[var(--border)] bg-[var(--card)] px-8 py-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-[var(--text-soft)]">Platform console</p>
            <h1 className="mt-1 text-3xl font-semibold tracking-tight">Subscription plans</h1>
            <p className="mt-2 max-w-2xl text-sm text-[var(--text-soft)]">
              What each tier is sold as. A price left unset shows as &ldquo;not set&rdquo; rather than free.
            </p>
          </div>
          <button
            onClick={() => setEditing("new")}
            className="rounded-lg bg-[var(--primary)] px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-[var(--primary-hover)]"
          >
            + New plan
          </button>
        </div>
      </header>

      <main className="px-8 py-8">
        {isLoading && <p className="text-sm text-[var(--text-soft)]">Loading…</p>}
        {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}
        <div className="grid gap-6 lg:grid-cols-3">
          {(plans ?? []).map((plan) => (
            <PlanCard key={plan.id} plan={plan} onEdit={() => setEditing(plan)} />
          ))}
        </div>
      </main>

      {editing && <PlanDialog plan={editing === "new" ? null : editing} onClose={() => setEditing(null)} />}
    </div>
  );
}

function PlanCard({ plan, onEdit }: { plan: SubscriptionPlan; onEdit: () => void }) {
  const limitBits = [
    plan.price_monthly ? `${formatCedis(plan.price_monthly)}/mo` : null,
    plan.max_members ? `${plan.max_members.toLocaleString()} members` : "Unlimited members",
    plan.trial_days ? `${plan.trial_days}-day trial` : null,
    `${plan.community_count} communit${plan.community_count === 1 ? "y" : "ies"}`,
  ].filter(Boolean);

  return (
    <section
      className={`rounded-[var(--radius)] bg-[var(--card)] p-6 ${plan.is_active ? "" : "opacity-60"}`}
      style={{ boxShadow: "var(--shadow-sm)", border: "1px solid var(--border-soft)" }}
    >
      <div className="flex items-start justify-between gap-3">
        <h2 className="text-xl font-semibold">{plan.name}</h2>
        <button onClick={onEdit} className="text-sm font-medium text-[var(--primary)] hover:underline">Edit</button>
      </div>
      <p className="mt-3 text-xs uppercase tracking-wide text-[var(--text-soft)]">
        {plan.code.replace(/_/g, " ")}{plan.description ? ` · ${plan.description}` : ""}
      </p>
      <p className="mt-4 text-3xl font-semibold">
        {plan.price_yearly ? <>{formatCedis(plan.price_yearly)}<span className="text-base font-normal text-[var(--text-soft)]">/yr</span></> : <span className="text-lg font-medium text-[var(--text-soft)]">Price not set</span>}
      </p>
      <p className="mt-1 text-sm text-[var(--text-soft)]">{limitBits.join(" · ")}</p>
      {!plan.is_active && <p className="mt-2 text-xs font-medium text-[var(--clay-red)]">Retired — not offered to new communities</p>}
      <ul className="mt-5 grid grid-cols-1 gap-x-4 gap-y-1.5 sm:grid-cols-2">
        {plan.features.map((f, i) => (
          <li key={i} className="flex items-start gap-2 text-sm">
            <span aria-hidden className="mt-0.5 text-[var(--forest)]">✓</span>
            <span>{f}</span>
          </li>
        ))}
        {plan.features.length === 0 && <li className="text-xs text-[var(--text-soft)]">No features listed yet.</li>}
      </ul>
    </section>
  );
}

function PlanDialog({ plan, onClose }: { plan: SubscriptionPlan | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [code, setCode] = useState(plan?.code ?? "");
  const [name, setName] = useState(plan?.name ?? "");
  const [description, setDescription] = useState(plan?.description ?? "");
  const [priceYearly, setPriceYearly] = useState(plan?.price_yearly ?? "");
  const [priceMonthly, setPriceMonthly] = useState(plan?.price_monthly ?? "");
  const [maxMembers, setMaxMembers] = useState(plan?.max_members?.toString() ?? "");
  const [maxCommunities, setMaxCommunities] = useState(plan?.max_communities?.toString() ?? "1");
  const [trialDays, setTrialDays] = useState(plan?.trial_days?.toString() ?? "0");
  const [featuresText, setFeaturesText] = useState((plan?.features ?? []).join("\n"));
  const [isActive, setIsActive] = useState(plan?.is_active ?? true);

  const save = useMutation({
    mutationFn: () => {
      const input: SubscriptionPlanInput = {
        name: name.trim(),
        description: description.trim(),
        price_yearly: priceYearly.trim() || null,
        price_monthly: priceMonthly.trim() || null,
        max_members: maxMembers.trim() ? Number(maxMembers) : null,
        max_communities: Number(maxCommunities) || 1,
        trial_days: Number(trialDays) || 0,
        features: featuresText.split("\n").map((l) => l.trim()).filter(Boolean),
        is_active: isActive,
      };
      return plan ? tenantsApi.updateSubscriptionPlan(plan.id, input) : tenantsApi.createSubscriptionPlan({ ...input, code: code.trim(), name: name.trim() });
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["subscription-plans"] }); onClose(); },
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div
        role="dialog" aria-modal="true"
        className="font-body flex max-h-[85vh] w-full max-w-lg flex-col overflow-hidden rounded-[var(--radius)] bg-[var(--card)]"
        style={{ boxShadow: "var(--shadow-md)" }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="shrink-0 border-b border-[var(--border-soft)] p-6 pb-4">
          <h2 className="text-xl font-semibold">{plan ? `Edit ${plan.name}` : "New plan"}</h2>
          <p className="mt-1 text-sm text-[var(--text-soft)]">{plan ? "The code never changes — it's what every community on this plan refers to." : "A short code identifies the plan permanently; everything else can be edited later."}</p>
        </div>
        <form onSubmit={(e) => { e.preventDefault(); save.mutate(); }} className="overflow-y-auto p-6 pt-4">
          <div className="space-y-5">
            <FormSection label="Identity">
              {!plan && (
                <Field label="Code" hint="Lowercase, e.g. starter or enterprise_plus">
                  <input value={code} onChange={(e) => setCode(e.target.value)} className={FIELD_INPUT_CLASS} autoFocus />
                </Field>
              )}
              <Field label="Name" wide={Boolean(plan)}>
                <input value={name} onChange={(e) => setName(e.target.value)} className={FIELD_INPUT_CLASS} />
              </Field>
              <Field label="Description" wide>
                <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={2} className={FIELD_INPUT_CLASS} />
              </Field>
            </FormSection>
            <FormSection label="Pricing" hint="Leave blank to show as not set">
              <Field label="Per year (GH₵)"><input type="number" min="0" step="0.01" value={priceYearly} onChange={(e) => setPriceYearly(e.target.value)} className={FIELD_INPUT_CLASS} /></Field>
              <Field label="Per month (GH₵)"><input type="number" min="0" step="0.01" value={priceMonthly} onChange={(e) => setPriceMonthly(e.target.value)} className={FIELD_INPUT_CLASS} /></Field>
            </FormSection>
            <FormSection label="Limits">
              <Field label="Max members" hint="Blank = unlimited"><input type="number" min="1" value={maxMembers} onChange={(e) => setMaxMembers(e.target.value)} className={FIELD_INPUT_CLASS} /></Field>
              <Field label="Max communities"><input type="number" min="1" value={maxCommunities} onChange={(e) => setMaxCommunities(e.target.value)} className={FIELD_INPUT_CLASS} /></Field>
              <Field label="Trial days"><input type="number" min="0" value={trialDays} onChange={(e) => setTrialDays(e.target.value)} className={FIELD_INPUT_CLASS} /></Field>
              <Field label="Offered to new communities">
                <label className="flex items-center gap-2 py-2 text-sm"><input type="checkbox" checked={isActive} onChange={(e) => setIsActive(e.target.checked)} /> Active</label>
              </Field>
            </FormSection>
            <FormSection label="Features" hint="One per line — shown as the checklist on the plan card">
              <Field label="Included features" wide>
                <textarea value={featuresText} onChange={(e) => setFeaturesText(e.target.value)} rows={6} className={FIELD_INPUT_CLASS} />
              </Field>
            </FormSection>
          </div>
          {save.isError && <p className="mt-3 text-sm text-[var(--clay-red)]">{save.error.message}</p>}
          <div className="mt-5 flex justify-end gap-2 border-t border-[var(--border-soft)] pt-4">
            <button type="button" onClick={onClose} className="px-3 py-2 text-sm text-[var(--text-soft)]">Cancel</button>
            <button type="submit" disabled={save.isPending || !name.trim() || (!plan && !code.trim())} className="rounded-lg bg-[var(--primary)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60">
              {save.isPending ? "Saving…" : plan ? "Save changes" : "Create plan"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
