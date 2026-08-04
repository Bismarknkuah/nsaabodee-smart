"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import Link from "next/link";
import { useContributionRules, useContributionRuleActions, usePreviewObligations } from "@/lib/hooks/useContributionRules";
import { formatCedis } from "@/lib/formatCedis";

const STATUS_LABEL: Record<string, string> = { active: "Active", inactive: "Inactive", deceased: "Deceased" };

export default function ContributionRulesPage() {
  const { data: rules, isLoading } = useContributionRules();
  const { updateGeneralRates, updateFamilyTierRates, setStatusExemption, updateDefaulterThresholds } = useContributionRuleActions();

  const [maleAmount, setMaleAmount] = useState("");
  const [femaleAmount, setFemaleAmount] = useState("");
  const [headAmount, setHeadAmount] = useState("");
  const [seniorAmount, setSeniorAmount] = useState("");
  const [juniorAmount, setJuniorAmount] = useState("");
  const [womanAmount, setWomanAmount] = useState("");
  const [townLeaderAmount, setTownLeaderAmount] = useState("");
  const [warning, setWarning] = useState("");
  const [highWarning, setHighWarning] = useState("");
  const [flag, setFlag] = useState("");

  const [previewFamilyId, setPreviewFamilyId] = useState("");
  const preview = usePreviewObligations();

  if (isLoading || !rules) return <div className="min-h-screen bg-[var(--paper)] px-8 py-6 text-sm text-[var(--ink-soft)]">Loading rules…</div>;

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">Community Administration</p>
        <h1 className="font-display mt-1 text-4xl">Contribution Rules</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          Everything that decides who pays what, in one place: the community&apos;s general
          rate, every family&apos;s own rate, who&apos;s exempt, and when someone gets flagged
          as a defaulter.
        </p>
      </header>

      <main className="grid gap-6 px-8 py-8 lg:grid-cols-2">
        {/* General rates */}
        <section className="border border-[var(--rule)] bg-white p-5">
          <h2 className="font-display text-lg">General rate (everyone outside the deceased&apos;s family)</h2>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">
            Currently {formatCedis(rules.general_rates.male_amount)} (male) /{" "}
            {formatCedis(rules.general_rates.female_amount)} (female)
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!maleAmount || !femaleAmount) return;
              updateGeneralRates.mutate(
                { male: maleAmount, female: femaleAmount },
                { onSuccess: () => { setMaleAmount(""); setFemaleAmount(""); } }
              );
            }}
            className="mt-3 flex flex-wrap items-end gap-3"
          >
            <div>
              <label className="text-xs font-medium">New male rate</label>
              <input
                type="number" min="0.01" step="0.01" value={maleAmount}
                onChange={(e) => setMaleAmount(e.target.value)}
                placeholder={rules.general_rates.male_amount}
                className="mt-1 block w-28 rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
              />
            </div>
            <div>
              <label className="text-xs font-medium">New female rate</label>
              <input
                type="number" min="0.01" step="0.01" value={femaleAmount}
                onChange={(e) => setFemaleAmount(e.target.value)}
                placeholder={rules.general_rates.female_amount}
                className="mt-1 block w-28 rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
              />
            </div>
            <button
              type="submit"
              disabled={updateGeneralRates.isPending}
              className="rounded-sm bg-[var(--forest)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-60"
            >
              Save
            </button>
          </form>
          <p className="mt-2 text-xs text-[var(--ink-soft)]">
            Changing this never rewrites funerals already open or closed — only new funerals
            created afterwards use the new rate.
          </p>
        </section>

        {/* Family tier rates */}
        <section className="rounded-sm border-2 border-[var(--gold)] bg-white p-5">
          <h2 className="font-display text-lg">The deceased&apos;s own family — tiered rates</h2>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">
            Currently head {formatCedis(rules.family_tier_rates.head_amount)} · uncle-tier{" "}
            {formatCedis(rules.family_tier_rates.senior_amount)} · nephew-tier{" "}
            {formatCedis(rules.family_tier_rates.junior_amount)} · women{" "}
            {formatCedis(rules.family_tier_rates.woman_amount)} · town leaders{" "}
            {formatCedis(rules.family_tier_rates.town_leader_amount)}
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!headAmount || !seniorAmount || !juniorAmount || !womanAmount || !townLeaderAmount) return;
              updateFamilyTierRates.mutate(
                {
                  head_amount: headAmount, senior_amount: seniorAmount, junior_amount: juniorAmount,
                  woman_amount: womanAmount, town_leader_amount: townLeaderAmount,
                },
                {
                  onSuccess: () => {
                    setHeadAmount(""); setSeniorAmount(""); setJuniorAmount(""); setWomanAmount(""); setTownLeaderAmount("");
                  },
                }
              );
            }}
            className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3"
          >
            <div>
              <label className="text-xs font-medium">Family head</label>
              <input type="number" min="0.01" step="0.01" value={headAmount} onChange={(e) => setHeadAmount(e.target.value)}
                placeholder={rules.family_tier_rates.head_amount}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]" />
            </div>
            <div>
              <label className="text-xs font-medium">Uncle tier (senior)</label>
              <input type="number" min="0.01" step="0.01" value={seniorAmount} onChange={(e) => setSeniorAmount(e.target.value)}
                placeholder={rules.family_tier_rates.senior_amount}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]" />
            </div>
            <div>
              <label className="text-xs font-medium">Nephew tier (junior)</label>
              <input type="number" min="0.01" step="0.01" value={juniorAmount} onChange={(e) => setJuniorAmount(e.target.value)}
                placeholder={rules.family_tier_rates.junior_amount}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]" />
            </div>
            <div>
              <label className="text-xs font-medium">Women</label>
              <input type="number" min="0.01" step="0.01" value={womanAmount} onChange={(e) => setWomanAmount(e.target.value)}
                placeholder={rules.family_tier_rates.woman_amount}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]" />
            </div>
            <div>
              <label className="text-xs font-medium">Town leaders</label>
              <input type="number" min="0.01" step="0.01" value={townLeaderAmount} onChange={(e) => setTownLeaderAmount(e.target.value)}
                placeholder={rules.family_tier_rates.town_leader_amount}
                className="mt-1 w-full rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]" />
            </div>
            <div className="flex items-end">
              <button
                type="submit"
                disabled={updateFamilyTierRates.isPending}
                className="w-full rounded-sm bg-[var(--gold)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-60"
              >
                Save
              </button>
            </div>
          </form>
          <p className="mt-2 text-xs text-[var(--ink-soft)]">
            Town leaders pay their own flat rate regardless of which family they belong to,
            overriding both the family and general rates entirely.
          </p>
        </section>

        {/* Defaulter thresholds */}
        <section className="border border-[var(--rule)] bg-white p-5">
          <h2 className="font-display text-lg">Defaulter thresholds</h2>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">
            Currently: miss {rules.defaulter_thresholds.warning} → Warning, miss{" "}
            {rules.defaulter_thresholds.high_warning} → High warning, miss{" "}
            {rules.defaulter_thresholds.flag} → Flagged (Family Head &amp; Treasurer notified).
          </p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (!warning || !highWarning || !flag) return;
              updateDefaulterThresholds.mutate(
                { warning: Number(warning), highWarning: Number(highWarning), flag: Number(flag) },
                { onSuccess: () => { setWarning(""); setHighWarning(""); setFlag(""); } }
              );
            }}
            className="mt-3 flex flex-wrap items-end gap-3"
          >
            {[
              { label: "Warning at", value: warning, set: setWarning, placeholder: rules.defaulter_thresholds.warning },
              { label: "High warning at", value: highWarning, set: setHighWarning, placeholder: rules.defaulter_thresholds.high_warning },
              { label: "Flag at", value: flag, set: setFlag, placeholder: rules.defaulter_thresholds.flag },
            ].map((f) => (
              <div key={f.label}>
                <label className="text-xs font-medium">{f.label}</label>
                <input
                  type="number" min="1" value={f.value} onChange={(e) => f.set(e.target.value)}
                  placeholder={String(f.placeholder)}
                  className="mt-1 block w-20 rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
                />
              </div>
            ))}
            <button
              type="submit"
              disabled={updateDefaulterThresholds.isPending}
              className="rounded-sm bg-[var(--forest)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-60"
            >
              Save
            </button>
          </form>
          {updateDefaulterThresholds.isError && (
            <p className="mt-2 text-sm text-[var(--clay-red)]">{updateDefaulterThresholds.error.message}</p>
          )}
        </section>

        {/* Member status exemptions */}
        <section className="border border-[var(--rule)] bg-white p-5">
          <h2 className="font-display text-lg">Who&apos;s exempt from mandatory contributions</h2>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">By member status, community-wide.</p>
          <ul className="mt-3 divide-y divide-[var(--rule)]">
            {rules.member_status_exemptions.map((rule) => (
              <li key={rule.status} className="flex items-center justify-between py-2 text-sm">
                <span>
                  {STATUS_LABEL[rule.status]}
                  {rule.is_default && <span className="ml-2 text-xs text-[var(--ink-soft)]">(default)</span>}
                </span>
                <label className="flex items-center gap-2">
                  <span className="text-xs text-[var(--ink-soft)]">{rule.is_exempt ? "Exempt" : "Pays"}</span>
                  <input
                    type="checkbox"
                    checked={rule.is_exempt}
                    onChange={(e) => setStatusExemption.mutate({ status: rule.status, isExempt: e.target.checked })}
                  />
                </label>
              </li>
            ))}
          </ul>
        </section>

        {/* Family rates */}
        <section className="border border-[var(--rule)] bg-white p-5">
          <h2 className="font-display text-lg">Own-family rates</h2>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">
            Set by each Family Head, approved here or in the Family Registry.
          </p>
          <ul className="mt-3 divide-y divide-[var(--rule)]">
            {rules.family_rates.map((f) => (
              <li key={f.family_id} className="flex items-center justify-between py-2 text-sm">
                <span>{f.family_name}</span>
                <span className="font-mono">
                  {f.standing_rate ? formatCedis(f.standing_rate) : "Not set"}
                  {f.recommended_rate && (
                    <span className="ml-2 text-xs text-[var(--gold)]">
                      ({formatCedis(f.recommended_rate)} pending)
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ul>
          <Link href="/families" className="mt-3 inline-block text-sm text-[var(--forest)] hover:underline">
            Manage family rates in the Family Registry →
          </Link>
        </section>

        {/* Preview */}
        <section className="border border-[var(--rule)] bg-white p-5 lg:col-span-2">
          <h2 className="font-display text-lg">Preview a funeral before creating one</h2>
          <p className="mt-1 text-sm text-[var(--ink-soft)]">
            See exactly what every member would owe under today&apos;s rules, without creating anything.
          </p>
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <div>
              <label className="text-xs font-medium">Deceased&apos;s family</label>
              <select
                value={previewFamilyId}
                onChange={(e) => setPreviewFamilyId(e.target.value)}
                className="mt-1 block w-56 rounded-sm border border-[var(--rule)] px-2 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
              >
                <option value="">Choose a family…</option>
                {rules.family_rates.map((f) => (
                  <option key={f.family_id} value={f.family_id}>{f.family_name}</option>
                ))}
              </select>
            </div>
            <button
              onClick={() => previewFamilyId && preview.mutate(previewFamilyId)}
              disabled={!previewFamilyId || preview.isPending}
              className="rounded-sm bg-[var(--ink)] px-4 py-1.5 text-sm font-medium text-white disabled:opacity-60"
            >
              Preview
            </button>
          </div>

          {preview.data && (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-sm bg-[var(--forest-soft)] p-3 text-sm">
                <p className="font-medium text-[var(--forest)]">Own family</p>
                {preview.data.requires_one_off_amount ? (
                  <p className="mt-1 text-[var(--clay-red)]">No approved rate — a one-off amount would be required.</p>
                ) : (
                  <p className="mt-1">
                    {preview.data.own_family_member_count} member(s) × {formatCedis(preview.data.own_family_amount!)}
                  </p>
                )}
              </div>
              <div className="rounded-sm bg-[var(--gold-soft)] p-3 text-sm">
                <p className="font-medium text-[var(--gold)]">Everyone else</p>
                <p className="mt-1">
                  {preview.data.general_male_member_count} male × {formatCedis(preview.data.general_male_amount)}
                </p>
                <p>
                  {preview.data.general_female_member_count} female × {formatCedis(preview.data.general_female_amount)}
                </p>
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
