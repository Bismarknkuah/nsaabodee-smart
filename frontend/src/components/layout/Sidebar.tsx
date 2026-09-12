"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { useAuthStore } from "@/store/authStore";
import { accountsApi } from "@/lib/api/accounts";
import { useOfflineSync } from "@/lib/hooks/useOfflineSync";
import { ChatbotWidget } from "@/components/chatbot/ChatbotWidget";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { formatRole } from "@/lib/formatRole";
import {
  IconDashboard, IconCommunities, IconFamilies, IconFunerals, IconDesk, IconSync,
  IconMembers, IconTasks, IconRules, IconReports, IconReceipt, IconGift, IconBell,
  IconInactive, IconAlert, IconMeeting, IconUser, IconSignOut, IconMenu, IconClose,
} from "@/components/icons/NavIcons";

const PLATFORM_TIER = ["platform_admin"];
// "The Super Administrator must not... manage community finances...
// access confidential financial records belonging to a community."
// Deliberately NOT spreading PLATFORM_TIER in here — same conflation
// just fixed on the backend (these roles were baked into every
// community-operational permission set as a "can do everything a
// Community Admin can" convenience). Showing a nav link the backend
// will now correctly reject is worse than not showing it at all.
const COMMUNITY_ADMIN_TIER = ["community_admin", "chairman", "secretary"];
const FINANCE_OVERSIGHT = [...COMMUNITY_ADMIN_TIER, "treasurer", "financial_secretary", "auditor"];
const FAMILY_OFFICERS = ["family_head", "family_secretary", "family_treasurer"];
// General browse/oversight access to funerals, members, and offline
// sync status — the whole committee's core duties, unrelated to
// hands-on Front Desk work. Kept separate from DESK_ROLES below after
// a real regression: narrowing DESK_ROLES to fix Front Desk's own
// visibility had accidentally also hidden "Funerals" and "Members"
// from Chairman/Secretary/Treasurer/Financial Secretary/Auditor
// entirely, since all four nav links shared one constant.
const FUNERAL_BROWSE_ROLES = [...FINANCE_OVERSIGHT, "collector", ...FAMILY_OFFICERS];
// 'Apart from the collector, no user-role type should have front
// desk features to collect money.' Narrowed to Collector only — a
// Family Head/Secretary/Treasurer who's actually been assigned and
// approved for a specific funeral's desk can still reach it via a
// direct link from their own dashboard (the same pattern already used
// for the family fund and a bereaved rep's own funeral), the same way
// this platform already avoids showing a page to roles who'd rarely
// need it as a standing nav item.
const DESK_ROLES = ["collector"];
const AUDIT_LOG_ROLES = ["platform_admin", "community_admin"];
// UPDATED: 'The Deceased Rep is not allowed to receive donations.
// Community members and executives with a personal dashboard... are
// set to receive donations.' Superseded the earlier "no executive can
// receive donations" rule — see gifts.services.register_donation_account_holder
// for the current, narrower restriction (Deceased Rep only). "My
// Donations Received" is accordingly visible to every role except
// Guest now, not just non-executives.
// 'The guest shouldn't have my donation and welfare contribution
// features as they are just visitors and they don't receive gift from
// anywhere.' Guest accounts are typically temporary, on-the-spot desk
// worker logins (see funerals.services.assign_desk_worker) — not real,
// standing community members with donation-account eligibility or
// welfare obligations of their own.
// Community-scoped, member-level features — a real task list, a real
// welfare obligation, a real receipt — that structurally don't apply
// to Platform Admin, who belongs to no single community at all.
// Showing these as "universal" nav links meant Platform Admin saw
// pages that would only ever be empty for them, not because nothing's
// there yet but because the entire concept doesn't apply to their
// role — a real "can this role execute their function" gap, not a
// crash, but confusing, irrelevant nav clutter that isn't fixed by
// waiting for data to appear.
const ALL_COMMUNITY_ROLES = [
  "community_admin", "chairman", "secretary", "treasurer", "financial_secretary", "auditor",
  "collector", "family_head", "family_secretary", "family_treasurer", "traditional_leader",
  "community_member", "guest", "bereaved_rep", "notification_officer",
];
// 'The leader executive dashboard should only be mainly for his role.
// So you can remove my receipt from his dashboard.' The Traditional
// Leader doesn't pay contributions themselves — this is member-level,
// personal-payment-history data that's structurally irrelevant to a
// role explicitly built as "oversight, not operations."
const ALL_COMMUNITY_ROLES_EXCEPT_LEADER = ALL_COMMUNITY_ROLES.filter((r) => r !== "traditional_leader");
// Same reasoning as NON_EXECUTIVE_ROLES above — a Guest is typically a
// temporary desk-worker login, not a standing member with real welfare
// obligations of their own.
const ALL_COMMUNITY_ROLES_EXCEPT_GUEST = ALL_COMMUNITY_ROLES.filter((r) => r !== "guest");

const NAV_LINKS: { href: string; label: string; icon: typeof IconDashboard; roles: string[] | null; section: string }[] = [
  { href: "/dashboard", label: "Dashboard", icon: IconDashboard, roles: null, section: "" },

  // Platform — platform_admin's own tier, cross-community by nature.
  { href: "/communities", label: "Communities", icon: IconCommunities, roles: PLATFORM_TIER, section: "Platform" },
  { href: "/platform-admins", label: "User Management", icon: IconCommunities, roles: PLATFORM_TIER, section: "Platform" },
  { href: "/system-settings", label: "System Settings", icon: IconCommunities, roles: PLATFORM_TIER, section: "Platform" },
  { href: "/feature-flags", label: "Feature Flags", icon: IconAlert, roles: PLATFORM_TIER, section: "Platform" },
  { href: "/revenue", label: "Revenue", icon: IconReceipt, roles: PLATFORM_TIER, section: "Platform" },
  { href: "/support-queue", label: "Support Queue", icon: IconAlert, roles: [...PLATFORM_TIER, "community_admin"], section: "Platform" },

  // Funerals & Collections — the day-to-day operational work.
  { href: "/funerals", label: "Funerals", icon: IconFunerals, roles: FUNERAL_BROWSE_ROLES, section: "Funerals & Collections" },
  { href: "/front-desk", label: "Front Desk", icon: IconDesk, roles: DESK_ROLES, section: "Funerals & Collections" },
  { href: "/pending-sync", label: "Pending Sync", icon: IconSync, roles: FUNERAL_BROWSE_ROLES, section: "Funerals & Collections" },
  { href: "/members", label: "Members", icon: IconMembers, roles: FUNERAL_BROWSE_ROLES, section: "Funerals & Collections" },
  { href: "/families", label: "Families", icon: IconFamilies, roles: COMMUNITY_ADMIN_TIER, section: "Funerals & Collections" },
  { href: "/inactive-members", label: "Inactive Members", icon: IconInactive, roles: COMMUNITY_ADMIN_TIER, section: "Funerals & Collections" },

  // Finance & Oversight — money in, money out, and who's watching it.
  { href: "/contribution-rules", label: "Contribution Rules", icon: IconRules, roles: FINANCE_OVERSIGHT, section: "Finance & Oversight" },
  { href: "/reports", label: "Reports", icon: IconReports, roles: [...FINANCE_OVERSIGHT, "traditional_leader"], section: "Finance & Oversight" },
  { href: "/town-elders-ledger", label: "Town Elders Ledger", icon: IconCommunities, roles: ["traditional_leader", "community_admin", "chairman", "secretary"], section: "Finance & Oversight" },
  { href: "/ledger-wallets", label: "Ledger Wallets", icon: IconReceipt, roles: ["community_admin", "treasurer", "financial_secretary", "traditional_leader", "family_head", "family_treasurer"], section: "Finance & Oversight" },
  { href: "/suspicious-transactions", label: "Suspicious Transactions", icon: IconAlert, roles: FINANCE_OVERSIGHT, section: "Finance & Oversight" },
  // 'Collectors should have access to edit, especially when they make
  // mistakes.' Extended to Collector specifically for this — they can
  // only ever request a reversal for a payment they themselves
  // collected (enforced server-side), never anyone else's.
  { href: "/payment-reversals", label: "Payment Reversals", icon: IconAlert, roles: [...FINANCE_OVERSIGHT, "collector"], section: "Finance & Oversight" },
  { href: "/expenses", label: "Expenses", icon: IconAlert, roles: ["community_admin", "treasurer", "financial_secretary", "auditor"], section: "Finance & Oversight" },
  { href: "/liabilities", label: "Liabilities", icon: IconAlert, roles: ["community_admin", "treasurer", "financial_secretary", "auditor"], section: "Finance & Oversight" },
  { href: "/my-family-expenses", label: "Family Expenses", icon: IconAlert, roles: FAMILY_OFFICERS, section: "Finance & Oversight" },

  // Administration — who's in charge of what, and the paper trail behind it.
  { href: "/user-management", label: "User Management & Settings", icon: IconAlert, roles: ["community_admin", "family_head", "traditional_leader"], section: "Administration" },
  { href: "/collector-nominations", label: "Collector Nominations", icon: IconAlert, roles: ["community_admin", "chairman", "secretary", "treasurer", "traditional_leader", "family_head", "family_secretary", "family_treasurer"], section: "Administration" },
  { href: "/community-settings", label: "Community Settings", icon: IconAlert, roles: ["community_admin"], section: "Administration" },
  { href: "/meeting-summary", label: "Meeting Summary", icon: IconMeeting, roles: COMMUNITY_ADMIN_TIER, section: "Administration" },
  { href: "/notifications", label: "Notifications", icon: IconBell, roles: [...COMMUNITY_ADMIN_TIER, "notification_officer"], section: "Administration" },
  { href: "/audit-log", label: "Audit Log", icon: IconAlert, roles: AUDIT_LOG_ROLES, section: "Administration" },

  // Everyone's own — never grouped under a role-sounding header, since every role reaches these the same way.
  { href: "/tasks", label: "Tasks", icon: IconTasks, roles: ALL_COMMUNITY_ROLES, section: "My Space" },
  { href: "/welfare-contributions", label: "Welfare & Contributions", icon: IconReceipt, roles: ALL_COMMUNITY_ROLES_EXCEPT_GUEST, section: "My Space" },
  { href: "/my-receipts", label: "My Receipts", icon: IconReceipt, roles: ALL_COMMUNITY_ROLES_EXCEPT_LEADER, section: "My Space" },
  // Confirmed explicitly by the person despite the earlier flag: every
  // executive's personal account should look the same as a regular
  // member's, including this link. Structurally it will always read
  // empty for an executive (they can never be registered as a
  // donation recipient), but that's a data fact the page itself
  // already handles gracefully, not a reason to hide the link.
  { href: "/my-donations-received", label: "My Donations Received", icon: IconGift, roles: ALL_COMMUNITY_ROLES_EXCEPT_GUEST, section: "My Space" },
  { href: "/notice-board", label: "Notice Board", icon: IconBell, roles: null, section: "My Space" },
  { href: "/messaging", label: "Messaging", icon: IconBell, roles: null, section: "My Space" },
  // 'Only the community and temporary support should be moved or
  // reported to the platform admin.' Confirmed directly against
  // support.services: if Platform Admin ever submitted their own
  // ticket, neither _is_community_admin_ticket nor
  // _is_community_admin_of would ever match their role, leaving it
  // permanently unreachable by anyone, including themselves. They
  // already have Support Queue for receiving tickets — they never
  // need to submit one, so ALL_COMMUNITY_ROLES (which naturally
  // excludes platform_admin) is the right list here, not roles: null.
  { href: "/support", label: "Support", icon: IconAlert, roles: ALL_COMMUNITY_ROLES, section: "My Space" },
];

export function Sidebar({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const qc = useQueryClient();
  const [mobileOpen, setMobileOpen] = useState(false);
  // "Make sure all the user role types are having easier navigation."
  // A Community Admin can see 15+ links across five sections — a
  // quick filter narrows that to just what matches, without needing
  // to scan every section by eye. Purely client-side, over the
  // labels already visible — no new data, no new request.
  const [navFilter, setNavFilter] = useState("");

  // Auto-hide the moment a nav link is actually followed — a drawer
  // left open after navigating away defeats the whole point of it
  // auto-hiding "so the system looks professional" on a phone.
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);
  const { user, accessToken, refreshToken, clear, setUser } = useAuthStore();
  const { online, pendingCount, syncing } = useOfflineSync();

  // 'The executive should use their executive role dashboard for only
  // executive duties, and they shouldn't be able to use their personal
  // dashboard for executive duties but should use their personal
  // dashboards as any community members can.' Community Member and
  // Guest never have an executive side to switch away from at all
  // (they're not in the backend's EXECUTIVE_ROLES set and have no
  // separate switching path either), so they're always, inherently in
  // this same personal-style nav — active_context on their own account
  // defaults to "executive" purely as a DB-level default with no real
  // switch behind it, so that default alone must never be read as
  // "show them executive links."
  //
  // 'The Deceased Rep will also have to execute an executive role
  // type.' Deliberately NOT included here even though they can now
  // switch context (see accounts.models.User.can_switch_dashboard_context)
  // — that's a separate, narrower check specifically so donation
  // -recipient eligibility (which reads the same EXECUTIVE_ROLES set)
  // stays untouched. Their nav now properly follows active_context
  // like every other real executive.
  const NON_EXECUTIVE_ROLE_NAMES = ["community_member", "guest"];
  const inPersonalContext = Boolean(
    (user?.role && NON_EXECUTIVE_ROLE_NAMES.includes(user.role)) || user?.active_context === "personal"
  );
  // Genuinely useful regardless of context — neither an "executive
  // duty" nor a "personal member duty" specifically.
  const ALWAYS_VISIBLE_HREFS = new Set(["/dashboard", "/notice-board", "/messaging", "/support"]);
  // A real member's own, individual community life — what "the same as
  // any community member" concretely means. Hidden from Executive
  // context so executive duties and personal duties never blur
  // together, per 'remove my welfare & contribution from executive
  // role dashboard.'
  const PERSONAL_CONTEXT_HREFS = new Set(["/tasks", "/welfare-contributions", "/my-receipts", "/my-donations-received"]);

  const visibleLinks = NAV_LINKS.filter((link) => {
    const roleMatches = user?.is_superuser || link.roles === null || link.roles.includes(user?.role ?? "");
    if (!roleMatches) return false;
    // 'Select what they can do or should see in their dashboard.' A
    // Community Admin or Family Head's restriction on this specific
    // account, layered on top of whatever their role already grants —
    // never a grant beyond it, only ever a narrowing.
    if (!user?.is_superuser && user?.disabled_features?.includes(link.href)) return false;
    if (ALWAYS_VISIBLE_HREFS.has(link.href)) return true;
    return inPersonalContext ? PERSONAL_CONTEXT_HREFS.has(link.href) : !PERSONAL_CONTEXT_HREFS.has(link.href);
  });

  // 'Make sure all the user dashboard navigation is easier to use and
  // should be user friendly.' A role like Community Admin ends up
  // seeing 15+ links — one long, undifferentiated list is genuinely
  // hard to scan. Groups by the same `section` every link already
  // declares, in the order sections first appear, so a role with only
  // a couple of links from one section never sees an empty group —
  // each header only ever shows up alongside links this account can
  // actually use.
  const groupedLinks: { section: string; links: typeof visibleLinks }[] = [];
  const filteredLinks = navFilter.trim()
    ? visibleLinks.filter((link) => link.label.toLowerCase().includes(navFilter.trim().toLowerCase()))
    : visibleLinks;
  for (const link of filteredLinks) {
    const existing = groupedLinks.find((g) => g.section === link.section);
    if (existing) existing.links.push(link);
    else groupedLinks.push({ section: link.section, links: [link] });
  }

  const logout = async () => {
    if (accessToken && refreshToken) {
      try {
        await accountsApi.logout(accessToken, refreshToken);
      } catch {
        // Even offline, clicking "Sign out" should still sign this device out locally.
      }
    }
    clear();
    router.push("/login");
  };

  return (
    <div className="flex min-h-screen">
      {/* Backdrop — mobile only, closes the drawer on tap outside it */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/*
        "The multi-task feature at the left side should auto hide so
        when the user wants to see it, he has to click on the three
        dot or slash." On mobile this is a genuine off-canvas drawer,
        hidden by default (-translate-x-full), toggled by the hamburger
        button below. On desktop (md: and up) it's exactly what it
        always was: sticky, always visible, part of the normal layout.

        "When scrolling down on the main interface it shouldn't affect
        the task slide unless you're scrolling the multi task menu or
        section." Fixed here too: h-screen + sticky top-0 means this
        panel's own height is pinned to the viewport, never stretched
        to match a tall page's content — the only thing that scrolls
        inside it is the nav list itself (via its own overflow-y-auto
        below), completely independent of the main content's scroll.
      */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex h-screen w-64 shrink-0 flex-col bg-[#152922] text-[#e9ede9] transition-transform duration-200 ease-in-out md:sticky md:top-0 md:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Brand */}
        <div className="flex items-center gap-2.5 border-b border-white/10 px-5 py-5">
          <svg viewBox="0 0 40 40" className="h-8 w-8 shrink-0 text-[var(--gold,#c9a227)]" aria-hidden="true">
            <circle cx="20" cy="20" r="17" fill="none" stroke="currentColor" strokeWidth="1.4" />
            <circle cx="20" cy="20" r="4" fill="none" stroke="currentColor" strokeWidth="1.6" />
            {Array.from({ length: 8 }, (_, i) => {
              const a = (i / 8) * Math.PI * 2;
              return <circle key={i} cx={20 + Math.cos(a) * 13.5} cy={20 + Math.sin(a) * 13.5} r="1.6" fill="currentColor" />;
            })}
          </svg>
          <div className="min-w-0">
            <p className="font-display truncate text-sm font-medium leading-tight text-white">Nsaabodeɛ Smart</p>
            <p className="truncate text-[10px] uppercase tracking-wide text-white/50">{user?.community_name ?? "Platform"}</p>
          </div>
        </div>

        {/* User block */}
        <Link href="/profile" className="flex items-center gap-2.5 border-b border-white/10 px-5 py-4 hover:bg-white/5">
          {user?.profile_photo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={user.profile_photo_url} alt="" className="h-9 w-9 shrink-0 rounded-full object-cover" />
          ) : (
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-white/10 font-display text-sm text-white">
              {user?.username?.slice(0, 1).toUpperCase()}
            </span>
          )}
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-white">{user?.username}</p>
            <p className="truncate text-[10px] uppercase tracking-wide text-white/50">{formatRole(user?.role)}</p>
          </div>
        </Link>

        {/* "Switch to Personal Dashboard" — no logout, no new account, just a flip of context. "Refresh all menus and dashboards" — every cached query is invalidated, not just the one about to be shown, since a page visited moments ago in the other context must never quietly serve stale, wrong-context data if revisited. */}
        {user?.can_switch_dashboard_context && (
          <button
            onClick={async () => {
              const updated = await accountsApi.switchContext(user.active_context === "executive" ? "personal" : "executive");
              setUser(updated);
              await qc.invalidateQueries();
              router.push("/dashboard");
            }}
            className="mx-5 mt-2 flex items-center justify-between rounded-sm border border-white/15 px-3 py-2 text-[11px] font-medium text-white/80 hover:bg-white/5"
          >
            {user.active_context === "executive" ? "Switch to Personal Dashboard" : "Switch to Executive Dashboard"}
            <span aria-hidden>⇄</span>
          </button>
        )}

        {/* Connectivity */}
        <Link
          href="/pending-sync"
          className="mx-5 mt-3 flex items-center gap-1.5 rounded-full bg-white/5 px-3 py-1 text-[11px] font-medium text-white/70 hover:bg-white/10"
        >
          <span aria-hidden className={`h-1.5 w-1.5 rounded-full ${online ? "bg-emerald-400" : "bg-red-400"}`} />
          {online ? (syncing ? "Syncing…" : pendingCount > 0 ? `${pendingCount} pending sync` : "Online") : "Offline"}
        </Link>

        {/* Temporary/rental access warning — only shows for a community with a real deadline, and only once it's actually close or past. */}
        {user && (user.community_access_expired || (user.community_access_days_remaining !== null && user.community_access_days_remaining <= 7)) && (
          <div className={`mx-5 mt-2 rounded-sm px-3 py-2 text-[11px] ${user.community_access_expired ? "bg-red-500/20 text-red-200" : "bg-[var(--gold,#c9a227)]/20 text-[var(--gold,#c9a227)]"}`}>
            {user.community_access_expired
              ? "Access period has ended — contact your platform administrator."
              : `${user.community_access_days_remaining} day${user.community_access_days_remaining === 1 ? "" : "s"} of access remaining.`}
          </div>
        )}

        {/* Quick filter — only worth showing once there's actually enough to scan through. */}
        {visibleLinks.length > 6 && (
          <div className="mx-5 mt-3">
            <input
              value={navFilter}
              onChange={(e) => setNavFilter(e.target.value)}
              placeholder="Find a page…"
              aria-label="Filter navigation links"
              className="w-full rounded-sm border border-white/15 bg-white/5 px-3 py-1.5 text-[13px] text-white placeholder:text-white/40 outline-none focus:border-[var(--gold,#c9a227)]"
            />
          </div>
        )}

        {/* Nav */}
        <nav className="mt-3 flex-1 space-y-3 overflow-y-auto px-3 pb-3">
          {navFilter.trim() && groupedLinks.length === 0 && (
            <p className="px-2.5 py-2 text-sm text-white/50">No pages match &quot;{navFilter}&quot;.</p>
          )}
          {groupedLinks.map((group) => (
            <div key={group.section || "top"} className="space-y-0.5">
              {group.section && (
                <p className="px-2.5 pb-1 pt-2 text-[10px] uppercase tracking-widest text-white/40">{group.section}</p>
              )}
              {group.links.map((link) => {
                const active = pathname === link.href || pathname?.startsWith(`${link.href}/`);
                const Icon = link.icon;
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={`flex items-center gap-3 rounded-sm px-2.5 py-2 text-sm transition ${
                      active ? "bg-[var(--gold,#c9a227)] font-medium text-[#152922]" : "text-white/75 hover:bg-white/8 hover:text-white"
                    }`}
                  >
                    <Icon className="shrink-0" />
                    <span className="truncate">{link.label}</span>
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Account */}
        <div className="border-t border-white/10 px-3 py-3">
          <p className="px-2.5 pb-1 text-[10px] uppercase tracking-widest text-white/40">Account</p>
          <Link href="/profile" className="flex items-center gap-3 rounded-sm px-2.5 py-2 text-sm text-white/75 hover:bg-white/8 hover:text-white">
            <IconUser className="shrink-0" /> My Profile
          </Link>
          <button onClick={logout} className="flex w-full items-center gap-3 rounded-sm px-2.5 py-2 text-left text-sm text-white/75 hover:bg-white/8 hover:text-red-300">
            <IconSignOut className="shrink-0" /> Sign out
          </button>
        </div>
      </aside>

      <main className="min-w-0 flex-1 md:h-screen md:overflow-y-auto">
        {/* Mobile-only top bar with the hamburger toggle — "so when the user wants to see it, he has to click on the three dot or slash" */}
        <div className="sticky top-0 z-30 flex items-center gap-3 border-b border-[var(--rule)] bg-[var(--paper)] px-4 py-3 md:hidden">
          <button
            onClick={() => setMobileOpen((open) => !open)}
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileOpen}
            className="flex h-9 w-9 items-center justify-center rounded-sm border border-[var(--rule)] text-[var(--ink)]"
          >
            {mobileOpen ? <IconClose /> : <IconMenu />}
          </button>
          <span className="font-mono text-xs uppercase tracking-widest text-[var(--ink-soft)]">Nsaabodeɛ Smart</span>
        </div>
        <ErrorBoundary label="This page">{children}</ErrorBoundary>
      </main>
      <ErrorBoundary label="The help chat" fallback={null}>
        <ChatbotWidget />
      </ErrorBoundary>
    </div>
  );
}
