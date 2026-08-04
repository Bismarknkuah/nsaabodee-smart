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
// Narrower, specifically for the Front Desk work page itself — the
// broad community-wide oversight roles above don't do hands-on desk
// work, so this deliberately excludes them (see the front desk
// assignment workflow batch for the full reasoning).
const DESK_ROLES = ["community_admin", "collector", ...FAMILY_OFFICERS];
const AUDIT_LOG_ROLES = ["platform_admin", "community_admin"];
// 'No executive user role should have the button to receive
// donations' (see the donation-receiving permission overhaul batch —
// EXECUTIVE_ROLES there matches exactly). "My Donations Received" was
// showing to every role including every executive who can never
// legitimately have anything here — this is who's actually left once
// every executive role is excluded.
const NON_EXECUTIVE_ROLES = ["community_member", "guest", "bereaved_rep"];

const NAV_LINKS: { href: string; label: string; icon: typeof IconDashboard; roles: string[] | null }[] = [
  { href: "/dashboard", label: "Dashboard", icon: IconDashboard, roles: null },
  { href: "/communities", label: "Communities", icon: IconCommunities, roles: PLATFORM_TIER },
  { href: "/platform-admins", label: "Platform Administrators", icon: IconCommunities, roles: PLATFORM_TIER },
  { href: "/families", label: "Families", icon: IconFamilies, roles: COMMUNITY_ADMIN_TIER },
  { href: "/funerals", label: "Funerals", icon: IconFunerals, roles: FUNERAL_BROWSE_ROLES },
  { href: "/front-desk", label: "Front Desk", icon: IconDesk, roles: DESK_ROLES },
  { href: "/pending-sync", label: "Pending Sync", icon: IconSync, roles: FUNERAL_BROWSE_ROLES },
  { href: "/members", label: "Members", icon: IconMembers, roles: FUNERAL_BROWSE_ROLES },
  { href: "/tasks", label: "Tasks", icon: IconTasks, roles: null },
  { href: "/welfare-contributions", label: "Welfare & Contributions", icon: IconReceipt, roles: null },
  { href: "/contribution-rules", label: "Contribution Rules", icon: IconRules, roles: COMMUNITY_ADMIN_TIER },
  { href: "/reports", label: "Reports", icon: IconReports, roles: [...FINANCE_OVERSIGHT, "traditional_leader"] },
  { href: "/my-receipts", label: "My Receipts", icon: IconReceipt, roles: null },
  { href: "/my-donations-received", label: "My Donations Received", icon: IconGift, roles: NON_EXECUTIVE_ROLES },
  { href: "/notifications", label: "Notifications", icon: IconBell, roles: [...COMMUNITY_ADMIN_TIER, "notification_officer"] },
  { href: "/notice-board", label: "Notice Board", icon: IconBell, roles: null },
  { href: "/messaging", label: "Messaging", icon: IconBell, roles: null },
  { href: "/inactive-members", label: "Inactive Members", icon: IconInactive, roles: COMMUNITY_ADMIN_TIER },
  { href: "/suspicious-transactions", label: "Suspicious Transactions", icon: IconAlert, roles: FINANCE_OVERSIGHT },
  { href: "/payment-reversals", label: "Payment Reversals", icon: IconAlert, roles: FINANCE_OVERSIGHT },
  { href: "/expenses", label: "Expenses", icon: IconAlert, roles: ["community_admin", "treasurer", "financial_secretary"] },
  { href: "/liabilities", label: "Liabilities", icon: IconAlert, roles: ["community_admin", "treasurer", "financial_secretary"] },
  { href: "/community-settings", label: "Community Settings", icon: IconAlert, roles: ["community_admin"] },
  { href: "/audit-log", label: "Audit Log", icon: IconAlert, roles: AUDIT_LOG_ROLES },
  { href: "/support", label: "Support", icon: IconAlert, roles: null },
  { href: "/support-queue", label: "Support Queue", icon: IconAlert, roles: [...PLATFORM_TIER, "community_admin"] },
  { href: "/feature-flags", label: "Feature Flags", icon: IconAlert, roles: PLATFORM_TIER },
  { href: "/revenue", label: "Revenue", icon: IconReceipt, roles: PLATFORM_TIER },
  { href: "/meeting-summary", label: "Meeting Summary", icon: IconMeeting, roles: COMMUNITY_ADMIN_TIER },
];

export function Sidebar({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const qc = useQueryClient();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Auto-hide the moment a nav link is actually followed — a drawer
  // left open after navigating away defeats the whole point of it
  // auto-hiding "so the system looks professional" on a phone.
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);
  const { user, accessToken, refreshToken, clear, setUser } = useAuthStore();
  const { online, pendingCount, syncing } = useOfflineSync();

  const inPersonalContext = user?.active_context === "personal";
  const visibleLinks = NAV_LINKS.filter((link) => {
    if (inPersonalContext) return link.roles === null;
    return user?.is_superuser || link.roles === null || link.roles.includes(user?.role ?? "");
  });

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
            <p className="truncate text-[10px] uppercase tracking-wide text-white/50">{user?.role?.replace(/_/g, " ")}</p>
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

        {/* Nav */}
        <nav className="mt-3 flex-1 space-y-0.5 overflow-y-auto px-3 pb-3">
          {visibleLinks.map((link) => {
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
