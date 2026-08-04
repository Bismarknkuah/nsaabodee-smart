import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

/**
 * The real, confirmed root cause of the recurring "This page couldn't
 * load" crash for Chairman, Secretary, Treasurer, Financial Secretary,
 * and Auditor: dashboard/services.py sets
 * `include_gift_cash = user.is_superuser or user.role == Role.COMMUNITY_ADMIN`,
 * and reports/services.py's collections_report only ever adds the
 * `gift_cash` key when that flag is true —
 * `if gift_section is not None: result["gift_cash"] = gift_section`.
 * For every other community-tier and finance-tier role, `gift_cash` is
 * not present at all, not null, not zero — genuinely absent. The
 * frontend was accessing `.gift_cash.total` unconditionally, which
 * throws `Cannot read properties of undefined` the moment real data
 * (not the empty/undefined state during loading) reaches the page.
 *
 * This wasn't caught earlier because the very first manual check used
 * a Community Admin login — the one community-tier role that actually
 * does receive `gift_cash`. These tests use the exact shape every
 * other role genuinely receives, so this class of bug can never
 * silently reappear.
 */

vi.mock("@/store/authStore", () => ({
  useAuthStore: (selector: (s: { user: { username: string } }) => unknown) => selector({ user: { username: "demo_user" } }),
}));

const REAL_COMMUNITY_OVERVIEW_WITHOUT_GIFT_CASH = {
  active_funerals: 1,
  active_member_count: 20,
  family_count: 3,
  defaulter_count: 2,
  today_collections: {
    start_date: "2026-07-23",
    end_date: "2026-07-23",
    collector_id: null,
    contributions: { count: 1, total: "50", by_method: { cash: "50", mobile_money: "0", bank: "0", other: "0" } },
    combined_cash_position_by_method: { cash: "50", mobile_money: "0", bank: "0", other: "0" },
    receipts_issued: 1,
    // gift_cash deliberately absent — exactly what Chairman/Secretary actually receive
  },
  outstanding_members: { outstanding_member_count: 14 },
  recent_active_funerals: [{ id: "f1", deceased_name: "Demo Deceased", deceased_family_name: "Asona" }],
  collections_trend: [{ date: "2026-07-23", total: "50" }],
};

const REAL_FINANCIAL_OVERVIEW_WITHOUT_GIFT_CASH = {
  today: {
    contributions: { count: 1, total: "50" },
    combined_cash_position_by_method: { cash: "50", mobile_money: "0", bank: "0", other: "0" },
  },
  month_to_date: { contributions: { total: "50" } },
  expenses_month_to_date: { total: "0" },
  outstanding_members: { outstanding_member_count: 14 },
  collections_trend: [{ date: "2026-07-23", total: "50" }],
  pending_funeral_openings_count: 0,
  pending_payment_reversals_count: 0,
};


describe("Community dashboard — Chairman/Secretary's actual data shape", () => {
  it("renders without throwing when gift_cash is genuinely absent", async () => {
    vi.resetModules();
    vi.doMock("@/lib/api/dashboard", () => ({
      dashboardApi: { get: async () => ({ role: "chairman", sections: { community_overview: REAL_COMMUNITY_OVERVIEW_WITHOUT_GIFT_CASH } }) },
    }));
    const { default: CommunityDashboardPage } = await import("@/app/(dashboard)/dashboard/community/page");
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(
      <QueryClientProvider client={qc}>
        <CommunityDashboardPage />
      </QueryClientProvider>
    );

    expect(await screen.findByText(/Contributions collected today|Collected today/)).toBeTruthy();
  });
});

describe("Financial dashboard — Treasurer/Auditor/Financial Secretary's actual data shape", () => {
  it("renders without throwing when gift_cash is genuinely absent (it never exists for this role)", async () => {
    vi.resetModules();
    vi.doMock("@/lib/api/dashboard", () => ({
      dashboardApi: { get: async () => ({ role: "treasurer", sections: { financial_overview: REAL_FINANCIAL_OVERVIEW_WITHOUT_GIFT_CASH } }) },
    }));
    const { default: FinancialDashboardPage } = await import("@/app/(dashboard)/dashboard/financial/page");
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });

    render(
      <QueryClientProvider client={qc}>
        <FinancialDashboardPage />
      </QueryClientProvider>
    );

    expect(await screen.findByText("Contributions today")).toBeTruthy();
  });
});
