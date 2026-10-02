import { useAuthStore } from "@/store/authStore";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

let refreshInFlight: Promise<string | null> | null = null;

/**
 * Every API client's `request()` helper in this app calls through here
 * instead of raw `fetch`, so a single place is responsible for attaching
 * the bearer token and — the reason this exists rather than just reading
 * the store inline everywhere — silently refreshing an expired access
 * token and retrying ONCE before giving up. Without this, a collector's
 * 2-hour-old access token expiring mid-shift would surface as a confusing
 * "request failed" on whatever screen they happened to be on, rather
 * than the app quietly staying logged in the way a 30-day refresh token
 * is supposed to allow.
 *
 * If the refresh itself fails (refresh token expired or blacklisted),
 * the auth store is cleared — every page that cares should redirect to
 * /login when `useAuthStore().accessToken` is null, rather than this
 * function trying to navigate directly (it has no router context).
 */
export async function authFetch(path: string, init?: RequestInit): Promise<Response> {
  const doFetch = (token: string | null) =>
    fetch(`${BASE}/api${path}`, {
      ...init,
      headers: {
        ...(init?.headers ?? {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

  const state = useAuthStore.getState();
  let res = await doFetch(state.accessToken);

  if (res.status === 401 && state.refreshToken) {
    const newAccessToken = await refreshAccessToken(state.refreshToken);
    if (newAccessToken) {
      res = await doFetch(newAccessToken);
    } else {
      useAuthStore.getState().clear();
    }
  }

  return res;
}

async function refreshAccessToken(refreshToken: string): Promise<string | null> {
  // Coalesce concurrent refreshes — several list requests firing at once
  // when a page loads shouldn't each independently try to refresh and
  // rotate the same refresh token (ROTATE_REFRESH_TOKENS on the backend
  // means only the first rotation succeeds; the rest would fail).
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${BASE}/api/auth/refresh/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh: refreshToken }),
        });
        if (!res.ok) return null;
        const data = await res.json();
        useAuthStore.getState().setTokens(data.access, data.refresh ?? refreshToken);
        return data.access as string;
      } catch {
        return null;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}
