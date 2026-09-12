const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

import type { CurrentUser } from "@/store/authStore";
import { authFetch } from "./authFetch";

export const accountsApi = {
  demoLogin: async (role: string) => {
    const res = await fetch(`${BASE}/api/auth/demo-login/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? "Demo access isn't available right now.");
    }
    return res.json() as Promise<{ access: string; refresh: string }>;
  },

  login: async (username: string, password: string) => {
    const res = await fetch(`${BASE}/api/auth/login/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? "Incorrect username or password.");
    }
    return res.json() as Promise<{ access: string; refresh: string }>;
  },

  me: async (accessToken: string): Promise<CurrentUser> => {
    const res = await fetch(`${BASE}/api/auth/me/`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    if (!res.ok) throw new Error("Could not load your account.");
    return res.json();
  },

  /** "Switch to Personal Dashboard" — no logout, no new account, just a flip of context. */
  switchContext: async (context: "executive" | "personal"): Promise<CurrentUser> => {
    const res = await authFetch(`/auth/switch-context/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ context }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail?.toString() ?? body.non_field_errors?.[0] ?? "Could not switch dashboard context.");
    }
    return res.json();
  },

  /** Phone+OTP login — additive alongside username/password, not a replacement. */
  requestOtp: async (phoneNumber: string): Promise<{ demoCode?: string }> => {
    const res = await fetch(`${BASE}/api/auth/otp/request/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone_number: phoneNumber }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail?.toString() ?? body.phone_number?.[0] ?? body.non_field_errors?.[0] ?? "Could not send a code.");
    }
    const body = await res.json().catch(() => ({}));
    return { demoCode: body.demo_code };
  },

  verifyOtp: async (phoneNumber: string, code: string): Promise<{ access: string; refresh: string }> => {
    const res = await fetch(`${BASE}/api/auth/otp/verify/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone_number: phoneNumber, code }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail?.toString() ?? body.non_field_errors?.[0] ?? "That code is invalid or has expired.");
    }
    return res.json();
  },

  /** "Forgot password" — reuses the same SMS code already sent for OTP sign-in (see requestOtp above), then sets a new password and signs in immediately. */
  resetPasswordWithOtp: async (phoneNumber: string, code: string, newPassword: string): Promise<{ access: string; refresh: string }> => {
    const res = await fetch(`${BASE}/api/auth/otp/reset-password/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone_number: phoneNumber, code, new_password: newPassword }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail?.toString() ?? body.non_field_errors?.[0] ?? body.new_password?.[0] ?? "Could not reset your password.");
    }
    return res.json();
  },

  logout: async (accessToken: string, refreshToken: string) => {
    await fetch(`${BASE}/api/auth/logout/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${accessToken}` },
      body: JSON.stringify({ refresh: refreshToken }),
    });
  },

  /** "Should be able to change their profile and upload dp." Multipart so a photo can travel in the same request as the email field. */
  updateProfile: async (input: { email?: string; phone_number?: string; profile_photo?: File }): Promise<CurrentUser> => {
    const form = new FormData();
    if (input.email !== undefined) form.set("email", input.email);
    if (input.phone_number !== undefined) form.set("phone_number", input.phone_number);
    if (input.profile_photo) form.set("profile_photo", input.profile_photo);
    const res = await authFetch("/auth/me/", { method: "PATCH", body: form });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail?.toString() ?? body.phone_number?.[0] ?? "Could not update your profile.");
    }
    return res.json();
  },

  changePassword: async (currentPassword: string, newPassword: string): Promise<void> => {
    const res = await authFetch("/auth/change-password/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail?.toString() ?? body.current_password?.[0] ?? body.new_password?.[0] ?? "Could not change your password.");
    }
  },

  /** 'The community admin should also have user management... same as each family head.' Same endpoint serves both tiers — the backend decides what's manageable based on the caller's own role. */
  manageableUsers: async () => {
    const res = await authFetch(`/accounts/manageable-users/`);
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "Couldn't load manageable users.");
    return res.json() as Promise<{
      restrictable_features: Record<string, string>;
      own_family_id: string | null;
      own_family_name: string | null;
      users: { id: string; username: string; role: string; community_name: string | null; disabled_features: string[] }[];
    }>;
  },
  setDisabledFeatures: async (targetId: string, disabledFeatures: string[]) => {
    const res = await authFetch(`/accounts/manageable-users/disabled-features/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_id: targetId, disabled_features: disabledFeatures }),
    });
    if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? "Couldn't update this account's features.");
    return res.json() as Promise<{ id: string; username: string; disabled_features: string[] }>;
  },
};
