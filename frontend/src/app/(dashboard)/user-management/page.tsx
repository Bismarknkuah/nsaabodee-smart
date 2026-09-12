"use client";

import "@/styles/family-registry-tokens.css";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { accountsApi } from "@/lib/api/accounts";
import { useAuthStore } from "@/store/authStore";
import { formatRole } from "@/lib/formatRole";
import { useAssignFamilyOfficer } from "@/lib/hooks/useFamilyFunds";
import { collectorNominationsApi, membersApi } from "@/lib/api/members";
import { useAssignTask } from "@/lib/hooks/useTasks";

/**
 * 'The community admin should also have user management and system
 * settings where he can manage all the family head, community
 * executives, community leader, collectors... select what they can
 * do or should see in their dashboard. Same as each family head
 * should also have user management and system settings where they
 * can manage on their family.'
 *
 * One page, not two, and reused across both tiers — the backend's
 * manageable-users endpoint already decides what's manageable purely
 * from the caller's own role, so a single component genuinely serves
 * a Community Admin managing their community's executives and a
 * Family Head managing their own family identically, just with
 * different data underneath.
 */
export default function UserManagementPage() {
  const currentUser = useAuthStore((s) => s.user);
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({ queryKey: ["manageable-users"], queryFn: accountsApi.manageableUsers });
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const update = useMutation({
    mutationFn: ({ targetId, disabledFeatures }: { targetId: string; disabledFeatures: string[] }) =>
      accountsApi.setDisabledFeatures(targetId, disabledFeatures),
    // Same instant-feedback, rollback-on-failure behavior as System Settings above.
    onMutate: async ({ targetId, disabledFeatures }) => {
      await qc.cancelQueries({ queryKey: ["manageable-users"] });
      const previous = qc.getQueryData<{ restrictable_features: Record<string, string>; own_family_id: string | null; own_family_name: string | null; users: { id: string; username: string; role: string; community_name: string | null; disabled_features: string[] }[] }>(["manageable-users"]);
      if (previous) {
        qc.setQueryData(["manageable-users"], {
          ...previous,
          users: previous.users.map((u) => (u.id === targetId ? { ...u, disabled_features: disabledFeatures } : u)),
        });
      }
      return { previous };
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(["manageable-users"], context.previous);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["manageable-users"] }),
  });

  const isFamilyHead = currentUser?.role === "family_head";
  const isChief = currentUser?.role === "traditional_leader";

  return (
    <div className="font-body min-h-screen bg-[var(--paper)] text-[var(--ink)]">
      <header className="border-b-2 border-[var(--ink)] px-8 py-6">
        <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em] text-[var(--ink-soft)]">
          {isFamilyHead ? "Family Register" : isChief ? "Town Elders" : "Community Administration"}
        </p>
        <h1 className="font-display mt-1 text-4xl">User Management &amp; System Settings</h1>
        <p className="mt-2 max-w-2xl text-sm text-[var(--ink-soft)]">
          {isFamilyHead
            ? "Your own family's officers and members. Restricting a feature only ever takes something away — it can never grant more than that person's role already allows."
            : isChief
            ? "Everyone currently in the Town Elders group. Add new elders and their executives, restrict what they see, and assign them tasks — all from here."
            : "Every executive in your community — Family Heads, Chairman, Secretary, Treasurer, Financial Secretary, Auditor, Collectors, and the Traditional Leader. Ordinary community members stay each Family Head's own responsibility, never yours to manage here."}
        </p>
      </header>

      <main className="px-8 py-8">
        {isLoading && <p className="text-sm text-[var(--ink-soft)]">Loading…</p>}
        {error && <p className="text-sm text-[var(--clay-red)]">{(error as Error).message}</p>}

        {data && data.users.length === 0 && (
          <p className="text-sm text-[var(--ink-soft)]">
            {isFamilyHead ? "No officers or members are registered in your family yet." : isChief ? "No Town Elders are registered yet." : "No executives are registered in your community yet."}
          </p>
        )}

        {/*
          'Make the Family Head system settings have more options, to
          let some act as treasurer, family contribution and donation
          collector, and treasurer, secretary as well.' Consolidates
          what used to require a trip to the Family Fund page (officer
          appointment) and Collector Nominations (collector nomination)
          into this same "manage my family" experience — reusing both
          existing, already-tested actions rather than duplicating
          either one.
        */}
        {isFamilyHead && data?.own_family_id && (
          <FamilyRoleAssignmentPanel familyId={data.own_family_id} />
        )}

        {/*
          'The chief should also have user management and system
          settings features to manage town elders, including adding
          town elders and the town elders' executive, and assigning
          tasks to them.' Reuses transfer_to_town_elder (already
          extended to include the Chief) and the existing task
          -assignment action — this panel starts both, it doesn't
          duplicate either one.
        */}
        {isChief && <ChiefTownEldersPanel elders={data?.users ?? []} />}

        <ul className="divide-y divide-[var(--rule)] border-y-2 border-[var(--ink)]">
          {data?.users.map((u) => (
            <li key={u.id} className="py-4">
              <button onClick={() => setExpandedId(expandedId === u.id ? null : u.id)} className="flex w-full items-center justify-between text-left">
                <div>
                  <p className="text-sm font-medium">{u.username}</p>
                  <p className="text-xs text-[var(--ink-soft)]">
                    {formatRole(u.role)}
                    {u.community_name && ` · ${u.community_name}`}
                    {u.disabled_features.length > 0 && ` · ${u.disabled_features.length} feature(s) restricted`}
                  </p>
                </div>
                <span className="text-xs text-[var(--ink-soft)]">{expandedId === u.id ? "Close" : "Manage"}</span>
              </button>

              {expandedId === u.id && data && (
                <FeatureToggleList
                  restrictableFeatures={data.restrictable_features}
                  disabledFeatures={u.disabled_features}
                  onToggle={(features) => update.mutate({ targetId: u.id, disabledFeatures: features })}
                />
              )}
            </li>
          ))}
        </ul>
        {update.isError && <p className="mt-3 text-sm text-[var(--clay-red)]">{update.error.message}</p>}
      </main>
    </div>
  );
}

function FeatureToggleList({
  restrictableFeatures,
  disabledFeatures,
  onToggle,
}: {
  restrictableFeatures: Record<string, string>;
  disabledFeatures: string[];
  onToggle: (features: string[]) => void;
}) {
  return (
    <div className="mt-3 rounded-sm bg-[var(--surface)] p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">
        Checked = visible on their dashboard
      </p>
      <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3">
        {Object.entries(restrictableFeatures).map(([href, label]) => {
          const isEnabled = !disabledFeatures.includes(href);
          return (
            <label key={href} className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isEnabled}
                onChange={(e) => {
                  const next = e.target.checked
                    ? disabledFeatures.filter((f) => f !== href)
                    : [...disabledFeatures, href];
                  onToggle(next);
                }}
              />
              {label}
            </label>
          );
        })}
      </div>
    </div>
  );
}

type FamilyRoleTarget = "secretary" | "treasurer" | "family_collector" | "donation_collector";

const FAMILY_ROLE_LABEL: Record<FamilyRoleTarget, string> = {
  secretary: "Family Secretary",
  treasurer: "Family Treasurer",
  family_collector: "Family (Contribution) Collector",
  donation_collector: "Donation Collector",
};

/**
 * 'Let some act as treasurer, family contribution and donation
 * collector, and treasurer, secretary as well.' Secretary/Treasurer
 * take effect immediately (assignOfficer already exists and is
 * already tested); the two collector types go through the same
 * nomination-and-approval workflow every collector on this platform
 * requires — this panel starts that nomination, it doesn't bypass it.
 */
function FamilyRoleAssignmentPanel({ familyId }: { familyId: string }) {
  const assignOfficer = useAssignFamilyOfficer(familyId);
  const [query, setQuery] = useState("");
  const [target, setTarget] = useState<FamilyRoleTarget>("secretary");
  const [feedback, setFeedback] = useState<string | null>(null);

  const { data: memberResults } = useQuery({
    queryKey: ["family-role-assignment-search", query],
    queryFn: () => membersApi.list({ search: query, family: familyId }),
    enabled: query.trim().length >= 2,
  });

  const nominateCollector = useMutation({
    mutationFn: ({ memberId, type }: { memberId: string; type: "family" | "donation" }) =>
      collectorNominationsApi.nominate(memberId, type),
  });

  const handlePick = (memberId: string, memberName: string) => {
    setFeedback(null);
    if (target === "secretary" || target === "treasurer") {
      assignOfficer.mutate(
        { memberId, officerRole: target },
        { onSuccess: () => { setQuery(""); setFeedback(`${memberName} is now the Family ${target === "secretary" ? "Secretary" : "Treasurer"}.`); } }
      );
    } else {
      const collectorType = target === "family_collector" ? "family" : "donation";
      nominateCollector.mutate(
        { memberId, type: collectorType },
        { onSuccess: () => { setQuery(""); setFeedback(`${memberName} nominated as a ${FAMILY_ROLE_LABEL[target]} — awaiting the family Treasurer and Secretary's approval before they can start collecting.`); } }
      );
    }
  };

  const isPending = assignOfficer.isPending || nominateCollector.isPending;
  const error = assignOfficer.error ?? nominateCollector.error;

  return (
    <div className="mb-8 rounded-sm border border-[var(--rule)] bg-[var(--surface)] p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Assign a family role</p>
      <p className="mt-1 text-xs text-[var(--ink-soft)]">
        Secretary and Treasurer take effect right away. A Family or Donation Collector still needs
        the family's own Treasurer and Secretary to confirm before they can start collecting —
        this only starts that nomination.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <select
          value={target}
          onChange={(e) => { setTarget(e.target.value as FamilyRoleTarget); setFeedback(null); }}
          className="rounded-sm border border-[var(--rule)] bg-white px-2 py-1.5 text-sm"
        >
          {(Object.keys(FAMILY_ROLE_LABEL) as FamilyRoleTarget[]).map((key) => (
            <option key={key} value={key}>{FAMILY_ROLE_LABEL[key]}</option>
          ))}
        </select>
        <input
          value={query}
          onChange={(e) => { setQuery(e.target.value); setFeedback(null); }}
          placeholder="Search a family member…"
          className="min-w-[16rem] flex-1 rounded-sm border border-[var(--rule)] bg-white px-3 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
        />
      </div>
      {memberResults && memberResults.length > 0 && (
        <ul className="mt-2 max-h-32 divide-y divide-[var(--rule)] overflow-y-auto rounded-sm bg-white">
          {memberResults.map((m) => (
            <li key={m.id} className="flex items-center justify-between px-3 py-1.5 text-sm">
              <span>{m.full_name}</span>
              <button
                onClick={() => handlePick(m.id, m.full_name)}
                disabled={isPending}
                className="rounded-sm border border-[var(--rule)] px-2 py-1 text-xs font-medium hover:border-[var(--forest)] hover:text-[var(--forest)] disabled:opacity-50"
              >
                {target === "secretary" || target === "treasurer" ? "Assign" : "Nominate"}
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="mt-2 text-xs text-[var(--clay-red)]">{error.message}</p>}
      {feedback && <p className="mt-2 text-xs" style={{ color: "var(--forest)" }}>{feedback}</p>}
    </div>
  );
}

type TownElderTitle = "chief" | "queen_mother" | "linguist" | "other";

const TOWN_ELDER_TITLE_LABEL: Record<TownElderTitle, string> = {
  chief: "Chief",
  queen_mother: "Queen Mother",
  linguist: "Linguist",
  other: "Other Town Executive",
};

/**
 * 'The chief should also have user management and system settings
 * features to manage town elders, including adding town elders and
 * the town elders' executive, and assigning tasks to them.' Adding an
 * elder reuses transfer_to_town_elder exactly as-is (a title itself
 * IS what makes someone part of this group's "executive" — Chief,
 * Queen Mother, and Linguist are all just as much this panel's
 * concern as an ordinary elder is); assigning a task reuses the same
 * task-assignment action every other role already has.
 */
function ChiefTownEldersPanel({ elders }: { elders: { id: string; username: string }[] }) {
  const qc = useQueryClient();
  const [query, setQuery] = useState("");
  const [title, setTitle] = useState<TownElderTitle>("other");
  const [feedback, setFeedback] = useState<string | null>(null);

  const [taskElderQuery, setTaskElderQuery] = useState("");
  const [taskMemberId, setTaskMemberId] = useState("");
  const [taskTitle, setTaskTitle] = useState("");
  const [taskFeedback, setTaskFeedback] = useState<string | null>(null);

  const { data: memberResults } = useQuery({
    queryKey: ["chief-town-elder-search", query],
    queryFn: () => membersApi.list({ search: query }),
    enabled: query.trim().length >= 2,
  });

  // The task-assignment picker only ever searches among CURRENT elders
  // — narrowed client-side against the roster this page already
  // loaded, since membersApi.list has no "is_town_leader" filter of
  // its own to search by.
  const { data: taskMemberResults } = useQuery({
    queryKey: ["chief-town-elder-task-search", taskElderQuery],
    queryFn: () => membersApi.list({ search: taskElderQuery }),
    enabled: taskElderQuery.trim().length >= 2,
  });
  const elderUsernames = new Set(elders.map((e) => e.username));
  const taskEligibleResults = (taskMemberResults ?? []).filter((m) => m.linked_username && elderUsernames.has(m.linked_username));

  const transferToTownElder = useMutation({
    mutationFn: ({ memberId, title }: { memberId: string; title: TownElderTitle }) => membersApi.transferToTownElder(memberId, title),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["manageable-users"] });
      qc.invalidateQueries({ queryKey: ["town-elders-ledger"] });
      setQuery("");
      setFeedback(`Added as a Town Elder (${TOWN_ELDER_TITLE_LABEL[vars.title]}).`);
    },
  });

  const assignTask = useAssignTask();

  return (
    <div className="mb-8 space-y-4">
      <div className="rounded-sm border border-[var(--rule)] bg-[var(--surface)] p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Add a Town Elder or executive</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <select
            value={title}
            onChange={(e) => { setTitle(e.target.value as TownElderTitle); setFeedback(null); }}
            className="rounded-sm border border-[var(--rule)] bg-white px-2 py-1.5 text-sm"
          >
            {(Object.keys(TOWN_ELDER_TITLE_LABEL) as TownElderTitle[]).map((key) => (
              <option key={key} value={key}>{TOWN_ELDER_TITLE_LABEL[key]}</option>
            ))}
          </select>
          <input
            value={query}
            onChange={(e) => { setQuery(e.target.value); setFeedback(null); }}
            placeholder="Search a community member…"
            className="min-w-[16rem] flex-1 rounded-sm border border-[var(--rule)] bg-white px-3 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
          />
        </div>
        {memberResults && memberResults.length > 0 && query.trim().length >= 2 && (
          <ul className="mt-2 max-h-32 divide-y divide-[var(--rule)] overflow-y-auto rounded-sm bg-white">
            {memberResults.map((m) => (
              <li key={m.id} className="flex items-center justify-between px-3 py-1.5 text-sm">
                <span>{m.full_name}</span>
                <button
                  type="button"
                  onClick={() => transferToTownElder.mutate({ memberId: m.id, title })}
                  disabled={transferToTownElder.isPending}
                  className="rounded-sm border border-[var(--rule)] px-2 py-1 text-xs font-medium hover:border-[var(--forest)] hover:text-[var(--forest)] disabled:opacity-50"
                >
                  Add
                </button>
              </li>
            ))}
          </ul>
        )}
        {transferToTownElder.isError && <p className="mt-2 text-xs text-[var(--clay-red)]">{transferToTownElder.error.message}</p>}
        {feedback && <p className="mt-2 text-xs" style={{ color: "var(--forest)" }}>{feedback}</p>}
      </div>

      <div className="rounded-sm border border-[var(--rule)] bg-[var(--surface)] p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--ink-soft)]">Assign a task to a Town Elder</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <input
            value={taskElderQuery}
            onChange={(e) => { setTaskElderQuery(e.target.value); setTaskMemberId(""); setTaskFeedback(null); }}
            placeholder="Search an elder by name…"
            className="min-w-[14rem] flex-1 rounded-sm border border-[var(--rule)] bg-white px-3 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
          />
          <input
            value={taskTitle}
            onChange={(e) => { setTaskTitle(e.target.value); setTaskFeedback(null); }}
            placeholder="Task title…"
            className="min-w-[12rem] flex-1 rounded-sm border border-[var(--rule)] bg-white px-3 py-1.5 text-sm outline-none focus:border-[var(--forest)]"
          />
          <button
            type="button"
            disabled={!taskMemberId || !taskTitle.trim() || assignTask.isPending}
            onClick={() =>
              assignTask.mutate(
                { assigned_to_id: taskMemberId, title: taskTitle.trim() },
                {
                  onSuccess: () => {
                    setTaskElderQuery(""); setTaskMemberId(""); setTaskTitle("");
                    setTaskFeedback("Task assigned.");
                  },
                }
              )
            }
            className="rounded-sm bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
          >
            Assign
          </button>
        </div>
        {!taskMemberId && taskEligibleResults.length > 0 && taskElderQuery.trim().length >= 2 && (
          <ul className="mt-2 max-h-32 divide-y divide-[var(--rule)] overflow-y-auto rounded-sm bg-white">
            {taskEligibleResults.map((m) => (
              <li key={m.id}>
                <button
                  type="button"
                  onClick={() => { setTaskElderQuery(m.full_name); setTaskMemberId(m.id); }}
                  className="w-full px-3 py-1.5 text-left text-sm hover:bg-[var(--surface)]"
                >
                  {m.full_name}
                </button>
              </li>
            ))}
          </ul>
        )}
        {taskElderQuery.trim().length >= 2 && taskEligibleResults.length === 0 && !taskMemberId && (
          <p className="mt-2 text-xs text-[var(--ink-soft)]">No current Town Elder matches that name.</p>
        )}
        {assignTask.isError && <p className="mt-2 text-xs text-[var(--clay-red)]">{assignTask.error.message}</p>}
        {taskFeedback && <p className="mt-2 text-xs" style={{ color: "var(--forest)" }}>{taskFeedback}</p>}
      </div>
    </div>
  );
}
