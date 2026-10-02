import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, act } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import fixtures from "./fixtures/welfare.json";

/**
 * The welfare requests page against the REAL payloads the seeded demo returns
 * (`/api/welfare/requests/`, `/api/welfare/campaigns/`) — and the division of labour it must show:
 * a welfare manager DECIDES requests but never pays them out (money leaves through finance), a member sees
 * only their own request and can ask for support.
 */
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }), useSearchParams: () => new URLSearchParams() }));
vi.mock("@/store/authStore", () => ({ useAuthStore: (sel: (s: unknown) => unknown) => sel({ user: { role: "welfare_manager", username: "u" } }) }));

const DATA = fixtures as unknown as Record<string, { requests: unknown[]; campaigns: unknown[] }>;
afterEach(() => cleanup());

async function renderFor(persona: string) {
  vi.resetModules();
  const noop = vi.fn(async () => ({}));
  vi.doMock("@/lib/api/welfare", () => ({
    welfareApi: {
      listRequests: async () => DATA[persona].requests,
      listCampaigns: async () => DATA[persona].campaigns,
      decideRequest: noop, disburseRequest: noop, acknowledgeRequest: noop, submitRequest: noop,
    },
  }));
  const { default: Page } = await import("@/app/(dashboard)/welfare-requests/page");
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><Page /></QueryClientProvider>);
  await act(async () => { await new Promise((r) => setTimeout(r, 200)); });
}

describe("welfare requests page, real payloads", () => {
  it("the welfare manager decides the pending request, and the approved one is with finance", async () => {
    await renderFor("welfare_manager");
    expect(screen.queryAllByText(/Demo Community Member/).length).toBeGreaterThan(0);
    expect(screen.queryAllByText(/Demo Widow Ama/).length).toBeGreaterThan(0);
    expect(screen.queryAllByText("Approve").length).toBe(1);            // only the still-pending request can be decided
    expect(screen.queryAllByText("Decline").length).toBe(1);
    expect(screen.queryAllByText(/With finance for payout/).length).toBe(1);
    expect(screen.queryAllByText("Mark paid out").length).toBe(0);      // paying out is not the welfare manager's job
  }, 30000);

  it("a member sees their own request, can ask for support, and cannot decide anything", async () => {
    await renderFor("community_member");
    expect(screen.queryAllByText(/Ask for support/).length).toBeGreaterThan(0);
    expect(screen.queryAllByText("Approve").length).toBe(0);
    expect(screen.queryAllByText("Mark paid out").length).toBe(0);
  }, 30000);
});
