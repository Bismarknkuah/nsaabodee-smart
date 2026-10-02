import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, cleanup, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import fixtures from "./fixtures/dashboards.json";
import { DASHBOARD_ROUTE_BY_ROLE } from "@/lib/dashboardRoutes";

/**
 * Every demo persona's REAL dashboard payload (dumped from the seeded backend by
 * `manage.py dump_dashboard_fixtures`) rendered by the REAL page for its role.
 *
 * TypeScript proves a page's types line up; it cannot prove the page survives the data it actually
 * receives — a field genuinely absent for one role once crashed five dashboards in production. This
 * is the check that would have caught it, run for every role at every level.
 */

const state = vi.hoisted(() => ({ user: { role: "", username: "", is_superuser: false } as Record<string, unknown> }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn(), prefetch: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/dashboard",
  useParams: () => ({}),
}));
vi.mock("@/store/authStore", () => {
  const hook = (selector: (s: unknown) => unknown) => selector({ user: state.user, isAuthenticated: true });
  (hook as unknown as { getState: () => unknown }).getState = () => ({ user: state.user });
  return { useAuthStore: hook };
});
vi.mock("@/lib/hooks/useFamilies", async (importOriginal) => ({ ...(await importOriginal<Record<string, unknown>>()), useFamilies: () => ({ data: [], isLoading: false }) }));
vi.mock("@/lib/hooks/useOfflineSync", () => ({
  useOfflineSync: () => ({ pendingCount: 0, isOnline: true, isSyncing: false, lastSyncedAt: null, lastSync: null, syncNow: async () => {}, sync: async () => {}, refresh: async () => {} }),
}));

const PAGES: Record<string, () => Promise<{ default: React.ComponentType }>> = {
  "/dashboard/bereaved": () => import("@/app/(dashboard)/dashboard/bereaved/page"),
  "/dashboard/chief": () => import("@/app/(dashboard)/dashboard/chief/page"),
  "/dashboard/collector": () => import("@/app/(dashboard)/dashboard/collector/page"),
  "/dashboard/community": () => import("@/app/(dashboard)/dashboard/community/page"),
  "/dashboard/family": () => import("@/app/(dashboard)/dashboard/family/page"),
  "/dashboard/financial": () => import("@/app/(dashboard)/dashboard/financial/page"),
  "/dashboard/gifts": () => import("@/app/(dashboard)/dashboard/gifts/page"),
  "/dashboard/member": () => import("@/app/(dashboard)/dashboard/member/page"),
  "/dashboard/platform": () => import("@/app/(dashboard)/dashboard/platform/page"),
  "/dashboard/registration": () => import("@/app/(dashboard)/dashboard/registration/page"),
  "/dashboard/welfare": () => import("@/app/(dashboard)/dashboard/welfare/page"),
};

// What each redesigned dashboard must actually SHOW, not merely survive.
const MUST_SHOW: Record<string, RegExp[]> = {
  chairman: [/Full oversight, approvals/, /Pending approvals/, /Contribution trends/, /Recent approvals/, /Approve funeral openings/],
  secretary: [/Manage records, communication/, /Announcements/, /Recent announcements/, /Create announcement/, /Manage documents/],
  traditional_leader: [/Track elders, roles and community matters/, /Total elders/, /Elders overview/, /View elders' ledger/],
  platform_admin: [/System management, users, settings/, /Total communities/, /Recent users/, /System health/, /Manage users/],
  town_registration_officer: [/Handle town members, registrations/, /Total town members/, /Recent registrations/, /Register member/],
  community_member: [/Total contributions/, /Outstanding balance/, /Recent payments/, /Contribution summary/, /Quick actions/, /Recent announcements/, /Member ID/],
  family_head: [/Family Executive Dashboard/, /Total members/, /Collections overview/, /Recent transactions/, /Quick shortcuts/, /Manage users/],
  family_treasurer: [/Total members/, /Collections overview/, /Recent transactions/],
  collector: [/Your jurisdiction/, /Who to chase/, /Today's handover/, /Your latest entries/, /whole community/],
  family_collector: [/Your jurisdiction/, /Who to chase/, /Asona family/],
  town_elders_collector: [/Your jurisdiction/, /Who to chase/, /Town Elders/],
  gift_collector: [/Your jurisdiction/],
  town_registration_officer: [/Records to complete/, /Town Elders register/, /Ledger activity/],
  family_registration_officer: [/Records to complete/],
  welfare_manager: [/Requests to decide/, /Approved — waiting on finance/, /Demo Community Member/, /Demo Widow Ama/],
};
const MUST_NOT_SHOW: Record<string, RegExp[]> = {
  secretary: [/Contribution trends/, /Pending approvals/],   // the Secretary's home is records and communication, not the Chairman's approvals
  family_treasurer: [/Manage users/],                       // the treasurer manages no users
  community_member: [/Record payment/, /Manage users/, /Add member/],   // a member takes no money and manages nothing
  family_registration_officer: [/Town Elders register/],   // the elders' register is the community registrar's alone
};

const DATA = fixtures as unknown as Record<string, { role: string; dashboard: unknown }>;
let errors: string[];

beforeEach(() => {
  errors = [];
  vi.spyOn(console, "error").mockImplementation((...args: unknown[]) => { errors.push(args.map(String).join(" ")); });
  vi.stubGlobal("fetch", () => Promise.reject(new Error("offline in test")));   // secondary hooks fail closed, quietly
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe("every persona's real dashboard payload renders in the real page for its role", () => {
  it.each(Object.keys(DATA))("%s", async (persona) => {
    const fx = DATA[persona];
    state.user = { role: fx.role, username: `demo_${persona}`, is_superuser: false, community: "demo" };
    vi.resetModules();
    vi.doMock("@/lib/api/dashboard", () => ({ dashboardApi: { get: async () => fx.dashboard } }));

    const route = DASHBOARD_ROUTE_BY_ROLE[fx.role];
    expect(route, `no dashboard route for role ${fx.role}`).toBeTruthy();
    const load = PAGES[route];
    expect(load, `no page registered in this test for ${route}`).toBeTruthy();
    const { default: Page } = await load();

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(<QueryClientProvider client={qc}><Page /></QueryClientProvider>);
    await act(async () => { await new Promise((r) => setTimeout(r, 200)); });

    const crashes = errors.filter((e) => /crashed:|Cannot read prop|is not a function|is not iterable|of undefined|of null/.test(e));
    expect(crashes, crashes.join("\n")).toEqual([]);
    expect(screen.queryByText(/couldn't load/i)).toBeNull();
    expect((container.textContent ?? "").length).toBeGreaterThan(60);

    for (const re of MUST_SHOW[persona] ?? []) expect(screen.queryAllByText(re).length, `${persona} should show ${re}`).toBeGreaterThan(0);
    for (const re of MUST_NOT_SHOW[persona] ?? []) expect(screen.queryAllByText(re).length, `${persona} must NOT show ${re}`).toBe(0);
  }, 30000);
});

describe("a partial payload degrades instead of taking the whole dashboard down", () => {
  it("collector with an empty takings block still renders its worklists", async () => {
    const fx = JSON.parse(JSON.stringify(DATA["collector"]));
    fx.dashboard.sections.collector_performance.my_takings = {};
    state.user = { role: "collector", username: "demo_collector", is_superuser: false };
    vi.resetModules();
    vi.doMock("@/lib/api/dashboard", () => ({ dashboardApi: { get: async () => fx.dashboard } }));
    const { default: Page } = await PAGES["/dashboard/collector"]();
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><Page /></QueryClientProvider>);
    await act(async () => { await new Promise((r) => setTimeout(r, 200)); });
    expect(errors.filter((e) => /crashed:|Cannot read prop/.test(e))).toEqual([]);
    expect(screen.queryAllByText(/Who to chase/).length).toBeGreaterThan(0);
  }, 30000);
});
