import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, cleanup, act, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import fixtures from "./fixtures/dashboards.json";

/**
 * The Front Desk — the collector's cashier screen — rendered against the real collector payload: today's collections
 * by method and the recent payments come from the same takings as the dashboard; the member search is the scoped
 * search (a family collector's results are their family's only, enforced on the server and asserted in the backend).
 */
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), useSearchParams: () => new URLSearchParams() }));
vi.mock("@/store/authStore", () => ({ useAuthStore: (sel: (s: unknown) => unknown) => sel({ user: { role: "collector", username: "demo_collector", ledger_scope: { level: "family", family_id: "f1", family_name: "Asona" } } }) }));
vi.mock("@/lib/hooks/useOnlineStatus", () => ({ useOnlineStatus: () => true }));
vi.mock("@/lib/hooks/useOfflineSync", () => ({ useOfflineSync: () => ({ online: true, pendingCount: 0, syncing: false, drainQueue: vi.fn(), refreshQueue: vi.fn() }) }));
vi.mock("@/lib/hooks/useDeskSession", () => ({ useDeskSession: () => ({ session: { collectorName: "Ama", deliveryMethod: "print", printMethod: "system" }, setSession: vi.fn(), clearSession: vi.fn(), hydrated: true }) }));
vi.mock("@/lib/offlineCache", () => ({ cacheMembers: vi.fn(), cacheObligations: vi.fn(), getCachedObligations: async () => [], searchCachedMembers: async () => [] }));
vi.mock("@/lib/offlineQueue", () => ({ enqueueOperation: vi.fn(), newClientOpId: () => "op-1" }));
vi.mock("@/components/QrScannerModal", () => ({ QrScannerModal: () => null, isQrScanningSupported: () => false, extractMemberIdFromScan: () => null }));

const DATA = fixtures as unknown as Record<string, { dashboard: unknown }>;
const member = { id: "m1", full_name: "Asona One", membership_number: "VTGH-00234", phone: "0244000001", status: "active", is_town_leader: false, family_detail: { id: "f1", name: "Asona" } };
const obligations = [{ obligation_id: "o1", funeral_id: "fu1", deceased_name: "Opanin", deceased_family_name: "Bretuo", rate_type: "general", expected_amount: "5.00", amount_paid: "2.00", balance: "3.00", payment_status: "partial" }];

beforeEach(() => {
  vi.resetModules();
  vi.doMock("@/lib/api/dashboard", () => ({ dashboardApi: { get: async () => DATA["collector"].dashboard } }));
  vi.doMock("@/lib/api/members", () => ({ membersApi: { list: async () => [member], get: async () => member }, arrearsApi: { lookup: async () => ({ arrears: [], current_bills: [], current_bills_payable: true }) } }));
  vi.doMock("@/lib/hooks/useReports", () => ({ useMemberOutstandingObligations: () => ({ data: obligations, isLoading: false, isSuccess: true }) }));
  vi.doMock("@/lib/api/funerals", () => ({ funeralsApi: { list: async () => ({ results: [] }), recordPayment: vi.fn(async () => ({ id: "p1" })), requestArrearsCorrection: vi.fn() } }));
  vi.doMock("@/lib/api/aiFeatures", () => ({ aiApi: { search: async () => [] } }));
  vi.doMock("@/lib/api/reports", () => ({ reportsApi: { receiptText: async () => "receipt" } }));
});
afterEach(() => cleanup());

describe("Front Desk, cashier layout, real collector payload", () => {
  it("shows today's collections by method, quick actions, and a member's account summary with the change calculation", async () => {
    const { default: Page } = await import("@/app/(dashboard)/front-desk/page");
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><Page /></QueryClientProvider>);
    await act(async () => { await new Promise((r) => setTimeout(r, 250)); });
    expect(screen.getAllByText(/Today's collections/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Total collections/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Quick actions/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Asona family ledger/).length).toBeGreaterThan(0);      // the jurisdiction note for a family collector

    fireEvent.change(screen.getByPlaceholderText(/name|phone|ID/i), { target: { value: "Asona" } });
    await act(async () => { await new Promise((r) => setTimeout(r, 250)); });
    fireEvent.click(screen.getAllByText("Asona One")[0]);
    await act(async () => { await new Promise((r) => setTimeout(r, 250)); });
    expect(screen.getAllByText(/Account summary/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("VTGH-00234").length).toBeGreaterThan(0);

    fireEvent.click(screen.getAllByText("Record payment")[0]);
    await act(async () => { await new Promise((r) => setTimeout(r, 50)); });
    expect(screen.getAllByText(/Payment details/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Mobile Money \(MoMo\)/).length).toBeGreaterThan(0);
    const received = screen.getByDisplayValue("3.00");
    fireEvent.change(received, { target: { value: "10" } });                          // pays with a GH₵10 note on a GH₵3 bill
    expect(screen.getAllByText(/Credit the GH₵7\.00 change/).length).toBeGreaterThan(0); // change computed, wallet offered
  }, 30000);
});
