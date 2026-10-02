import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup, fireEvent, waitFor } from "@testing-library/react";
import fixtures from "./fixtures/dashboards.json";

/**
 * The quick-login panel is a hard-coded list, so it can drift from the accounts the backend actually
 * seeds: a role renamed, dropped, or mistyped becomes a button that only fails when someone clicks it.
 * This clicks every button and checks the role it sends is one the backend really logged in
 * (the fixtures are exactly the personas whose demo login succeeded).
 */

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }), useSearchParams: () => new URLSearchParams() }));
vi.mock("@/store/authStore", () => ({ useAuthStore: (sel: (s: unknown) => unknown) => sel({ setSession: vi.fn(), login: vi.fn(), user: null }) }));

const sent: string[] = [];
vi.mock("@/lib/api/accounts", () => ({
  accountsApi: {
    demoLogin: async (role: string) => { sent.push(role); throw new Error("stop here — this test only records which role each button sends"); },
  },
}));

afterEach(() => { cleanup(); sent.length = 0; });

describe("grouped quick login", () => {
  it("shows the five groups, and every button sends a role the backend accepts", async () => {
    const { default: LoginPage } = await import("@/app/login/page");
    render(<LoginPage />);

    for (const title of ["Platform", "Community", "Family (Asona)", "Town Elders ledger", "Community members"]) {
      expect(screen.getAllByText(title).length, `missing group ${title}`).toBeGreaterThan(0);
    }

    // Every quick-access button lives inside a group grid; click each and record what it sends.
    const groupButtons = screen.getAllByRole("button").filter((b) => b.closest(".grid-cols-2") && /^(?!Show|Sign in)/.test(b.textContent ?? ""));
    expect(groupButtons.length).toBeGreaterThanOrEqual(18);
    for (const btn of groupButtons) {
      fireEvent.click(btn);
      await waitFor(() => expect((btn as HTMLButtonElement).disabled).toBe(false));   // demoRole resets in `finally`
    }

    const accepted = new Set(Object.keys(fixtures));
    const rejected = sent.filter((r) => !accepted.has(r));
    expect(rejected, `these buttons send a role the backend has no demo account for: ${rejected.join(", ")}`).toEqual([]);

    // The three-level collector, and both registrars, are reachable from the login page.
    for (const persona of ["collector", "family_collector", "town_elders_collector", "town_registration_officer", "family_registration_officer", "welfare_manager"]) {
      expect(sent, `no quick-login button for ${persona}`).toContain(persona);
    }
  }, 30000);
});
