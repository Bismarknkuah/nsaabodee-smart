import { create } from "zustand";

export interface CurrentUser {
  id: string;
  username: string;
  email: string;
  role: string;
  is_superuser: boolean;
  community: string | null;
  community_name: string | null;
  linked_member_id: string | null;
  linked_member_name: string | null;
  profile_photo_url: string | null;
  community_access_days_remaining: number | null;
  community_access_expired: boolean;
  phone_number: string | null;
  active_context: "executive" | "personal";
  can_switch_dashboard_context: boolean;
}

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  user: CurrentUser | null;
  setTokens: (access: string, refresh: string) => void;
  setUser: (user: CurrentUser) => void;
  clear: () => void;
  hydrate: () => void;
}

const STORAGE_KEY = "nsaabodee_auth";

function readStorage() {
  if (typeof window === "undefined") return { accessToken: null, refreshToken: null, user: null };
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : { accessToken: null, refreshToken: null, user: null };
  } catch {
    return { accessToken: null, refreshToken: null, user: null };
  }
}

function writeStorage(state: { accessToken: string | null; refreshToken: string | null; user: CurrentUser | null }) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

/**
 * A funeral-society collector's phone or laptop may go days between
 * logins during a quiet week — tokens persist in localStorage (not just
 * in-memory Zustand state) specifically so closing the browser tab
 * doesn't force a re-login every single time. The refresh token is
 * still short-of-forever (30 days, see backend SIMPLE_JWT settings) and
 * is blacklisted server-side on logout, so this isn't "never expires."
 */
export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  refreshToken: null,
  user: null,

  setTokens: (access, refresh) => {
    set((state) => {
      const next = { ...state, accessToken: access, refreshToken: refresh };
      writeStorage({ accessToken: access, refreshToken: refresh, user: state.user });
      return next;
    });
  },

  setUser: (user) => {
    set((state) => {
      writeStorage({ accessToken: state.accessToken, refreshToken: state.refreshToken, user });
      return { user };
    });
  },

  clear: () => {
    writeStorage({ accessToken: null, refreshToken: null, user: null });
    set({ accessToken: null, refreshToken: null, user: null });
  },

  hydrate: () => {
    const stored = readStorage();
    set({ accessToken: stored.accessToken, refreshToken: stored.refreshToken, user: stored.user });
  },
}));
