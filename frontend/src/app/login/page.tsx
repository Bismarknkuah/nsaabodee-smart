"use client";

import "@/styles/family-registry-tokens.css";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { accountsApi } from "@/lib/api/accounts";
import { useAuthStore } from "@/store/authStore";

const DEMO_ROLES: { value: string; label: string }[] = [
  { value: "platform_admin", label: "Platform Admin" },
  { value: "community_admin", label: "Community Admin" },
  { value: "traditional_leader", label: "Chief (Traditional Leader)" },
  { value: "chairman", label: "Chairman" },
  { value: "secretary", label: "Secretary" },
  { value: "treasurer", label: "Treasurer" },
  { value: "financial_secretary", label: "Financial Secretary" },
  { value: "auditor", label: "Auditor" },
  { value: "collector", label: "Collector" },
  { value: "family_head", label: "Family Head (Abusuapanin)" },
  { value: "family_secretary", label: "Family Secretary" },
  { value: "family_treasurer", label: "Family Treasurer" },
  { value: "community_member", label: "Community Member" },
  { value: "guest", label: "Guest" },
  { value: "bereaved_rep", label: "Bereaved Family Rep" },
  { value: "notification_officer", label: "Notification Officer" },
];

/**
 * "Failed to fetch" is what a browser's own fetch() throws for any
 * network-level failure — the backend being unreachable, offline, a
 * dropped connection — and it's a useless thing to show someone
 * actually trying to sign in. This turns that (and its handful of
 * common variants) into something a person can actually act on,
 * without masking a genuine "wrong password" response underneath it.
 */
function describeLoginError(err: unknown): string {
  const message = err instanceof Error ? err.message : "";
  if (/failed to fetch|networkerror|load failed/i.test(message)) {
    return "Could not reach the server. Check your internet connection and try again.";
  }
  return message || "Could not sign in.";
}

type Mode = "password" | "phone" | "forgot";

export default function LoginPage() {
  const router = useRouter();
  const setTokens = useAuthStore((s) => s.setTokens);
  const setUser = useAuthStore((s) => s.setUser);

  const [mode, setMode] = useState<Mode>("password");

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [demoRole, setDemoRole] = useState<string | null>(null);
  const [demoError, setDemoError] = useState<string | null>(null);

  const [phoneNumber, setPhoneNumber] = useState("");
  const [otpCode, setOtpCode] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otpLoading, setOtpLoading] = useState(false);
  const [otpError, setOtpError] = useState<string | null>(null);
  const [otpDemoCode, setOtpDemoCode] = useState<string | null>(null);

  const [resetPhone, setResetPhone] = useState("");
  const [resetCode, setResetCode] = useState("");
  const [resetNewPassword, setResetNewPassword] = useState("");
  const [resetSent, setResetSent] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetDemoCode, setResetDemoCode] = useState<string | null>(null);
  const [resetDone, setResetDone] = useState(false);

  const afterLogin = async (access: string, refresh: string) => {
    setTokens(access, refresh);
    const me = await accountsApi.me(access);
    setUser(me);
    router.push("/dashboard");
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const { access, refresh } = await accountsApi.login(username, password);
      await afterLogin(access, refresh);
    } catch (err) {
      setError(describeLoginError(err));
    } finally {
      setLoading(false);
    }
  };

  const sendCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setOtpError(null);
    setOtpDemoCode(null);
    setOtpLoading(true);
    try {
      const { demoCode } = await accountsApi.requestOtp(phoneNumber);
      if (demoCode) {
        // No real SMS provider configured yet — surface the code
        // directly and pre-fill it, so sign-in still actually works
        // rather than dead-ending on a code that was never sent.
        setOtpDemoCode(demoCode);
        setOtpCode(demoCode);
      }
      setOtpSent(true);
    } catch (err) {
      setOtpError(describeLoginError(err));
    } finally {
      setOtpLoading(false);
    }
  };

  const verifyCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setOtpError(null);
    setOtpLoading(true);
    try {
      const { access, refresh } = await accountsApi.verifyOtp(phoneNumber, otpCode);
      await afterLogin(access, refresh);
    } catch (err) {
      setOtpError(describeLoginError(err));
    } finally {
      setOtpLoading(false);
    }
  };

  const sendResetCode = async (e: React.FormEvent) => {
    e.preventDefault();
    setResetError(null);
    setResetDemoCode(null);
    setResetLoading(true);
    try {
      const { demoCode } = await accountsApi.requestOtp(resetPhone);
      if (demoCode) {
        setResetDemoCode(demoCode);
        setResetCode(demoCode);
      }
      setResetSent(true);
    } catch (err) {
      setResetError(describeLoginError(err));
    } finally {
      setResetLoading(false);
    }
  };

  const submitReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setResetError(null);
    setResetLoading(true);
    try {
      const { access, refresh } = await accountsApi.resetPasswordWithOtp(resetPhone, resetCode, resetNewPassword);
      setResetDone(true);
      await afterLogin(access, refresh);
    } catch (err) {
      setResetError(describeLoginError(err));
    } finally {
      setResetLoading(false);
    }
  };

  const tryDemo = async (role: string) => {
    setDemoError(null);
    setDemoRole(role);
    try {
      const { access, refresh } = await accountsApi.demoLogin(role);
      await afterLogin(access, refresh);
    } catch (err) {
      setDemoError(describeLoginError(err));
    } finally {
      setDemoRole(null);
    }
  };

  return (
    <div className="font-body flex min-h-screen">
      {/* Left panel — a real funeral hall as the backdrop, the same respectful, ceremonial register the whole platform is built around, with the forest-green brand tint over it rather than a flat color block */}
      <div className="relative hidden overflow-hidden lg:flex lg:w-[42%] lg:flex-col lg:justify-between lg:p-12">
        <div
          className="absolute inset-0 bg-cover bg-center"
          style={{ backgroundImage: "url('/login-hero.jpg')" }}
          aria-hidden="true"
        />
        <div
          className="absolute inset-0"
          style={{ background: "linear-gradient(160deg, rgba(12,25,18,0.75) 0%, rgba(20,38,28,0.55) 45%, rgba(12,25,18,0.4) 100%)" }}
          aria-hidden="true"
        />

        <Link href="/" className="relative z-10 font-mono text-xs uppercase tracking-[0.2em] text-white/80" style={{ textShadow: "0 1px 6px rgba(0,0,0,0.4)" }}>
          Nsaabodeɛ Smart
        </Link>

        <div className="relative z-10">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/10 px-3 py-1 text-[11px] font-medium uppercase tracking-wide text-white/90 backdrop-blur-sm">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--gold,#c9a227)]" />
            Trusted Community Platform
          </span>

          <p className="mt-6 font-mono text-[11px] uppercase tracking-[0.2em] text-white/70" style={{ textShadow: "0 1px 8px rgba(0,0,0,0.4)" }}>Welcome to</p>
          <p className="font-display mt-2 text-5xl leading-[1.05] text-white" style={{ textShadow: "0 2px 16px rgba(0,0,0,0.45)" }}>
            Nsaabodeɛ<br />Smart
          </p>
          <p className="mt-3 text-lg text-white/85" style={{ textShadow: "0 1px 10px rgba(0,0,0,0.4)" }}>Community Funeral &amp; Welfare Management</p>

          <p className="mt-6 max-w-xs text-sm text-white/70" style={{ textShadow: "0 1px 8px rgba(0,0,0,0.4)" }}>
            The same real ledgers your community already trusts — family dues, community
            dues, town elders, and guest gifts, kept honestly separate.
          </p>
        </div>

        <p className="relative z-10 font-mono text-[10px] uppercase tracking-wide text-white/50" style={{ textShadow: "0 1px 6px rgba(0,0,0,0.4)" }}>Powered by Desward Group Ltd</p>
      </div>

      {/* Right panel — the actual sign-in card */}
      <div className="flex flex-1 items-center justify-center bg-[var(--paper)] px-4 py-10">
      <div className="grid w-full max-w-4xl gap-8 lg:grid-cols-2">
        <div className="border border-[var(--rule)] bg-white p-8">
          <Link href="/" className="inline-flex items-center gap-1 font-mono text-xs uppercase tracking-widest text-[var(--ink-soft)] hover:text-[var(--forest)]">
            ← Back to homepage
          </Link>
          <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.2em] text-[var(--ink-soft)]">Folio · Sign In</p>
          <h1 className="font-display mt-1 text-3xl">Welcome back</h1>

          <div className="mt-5 flex gap-1 border border-[var(--rule)] bg-[var(--surface)] p-1 text-xs font-medium">
            <button
              type="button"
              onClick={() => setMode("password")}
              className={`flex-1 py-1.5 ${mode === "password" ? "bg-white shadow-sm" : "text-[var(--ink-soft)]"}`}
            >
              Password
            </button>
            <button
              type="button"
              onClick={() => setMode("phone")}
              className={`flex-1 py-1.5 ${mode === "phone" ? "bg-white shadow-sm" : "text-[var(--ink-soft)]"}`}
            >
              Phone Code
            </button>
          </div>

          {mode === "password" && (
          <form onSubmit={submit} className="mt-6 space-y-4">
            <div>
              <label className="font-mono text-[11px] font-medium uppercase tracking-wide text-[var(--ink-soft)]">Username</label>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoFocus
                autoComplete="username"
                className="mt-1 w-full border-0 border-b-2 border-[var(--rule)] bg-transparent px-0 py-2 text-sm outline-none focus:border-[var(--forest)]"
              />
            </div>
            <div>
              <div className="flex items-baseline justify-between">
                <label className="font-mono text-[11px] font-medium uppercase tracking-wide text-[var(--ink-soft)]">Password</label>
                <button type="button" onClick={() => setMode("forgot")} className="text-xs text-[var(--forest)] hover:underline">
                  Forgot password?
                </button>
              </div>
              <div className="relative mt-1">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  className="w-full border-0 border-b-2 border-[var(--rule)] bg-transparent px-0 py-2 pr-14 text-sm outline-none focus:border-[var(--forest)]"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute inset-y-0 right-0 text-xs font-medium text-[var(--ink-soft)] hover:text-[var(--forest)]"
                  tabIndex={-1}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>
            </div>

            {error && <p className="text-sm text-[var(--clay-red)]">{error}</p>}

            <button
              type="submit"
              disabled={loading || !username || !password}
              className="w-full bg-[var(--forest)] px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60"
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>
          )}

          {mode === "phone" && (
          <form onSubmit={otpSent ? verifyCode : sendCode} className="mt-6 space-y-4">
            <div>
              <label className="font-mono text-[11px] font-medium uppercase tracking-wide text-[var(--ink-soft)]">Phone number</label>
              <input
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                placeholder="+233 XX XXX XXXX"
                disabled={otpSent}
                autoFocus
                className="mt-1 w-full border-0 border-b-2 border-[var(--rule)] bg-transparent px-0 py-2 text-sm outline-none focus:border-[var(--forest)] disabled:text-[var(--ink-soft)]"
              />
            </div>

            {otpSent && (
              <div>
                <label className="font-mono text-[11px] font-medium uppercase tracking-wide text-[var(--ink-soft)]">One-time code</label>
                <input
                  value={otpCode}
                  onChange={(e) => setOtpCode(e.target.value)}
                  placeholder="6-digit code"
                  autoFocus
                  className="mt-1 w-full border-0 border-b-2 border-[var(--rule)] bg-transparent px-0 py-2 text-sm outline-none focus:border-[var(--forest)]"
                />
                {otpDemoCode && (
                  <p className="mt-2 rounded-sm border border-dashed border-[var(--gold)] bg-[var(--gold)]/10 px-3 py-2 text-xs text-[var(--ink)]">
                    SMS delivery isn&apos;t configured yet, so your code (<strong className="font-mono">{otpDemoCode}</strong>) has been filled in above automatically.
                  </p>
                )}
                <button
                  type="button"
                  onClick={() => { setOtpSent(false); setOtpCode(""); setOtpError(null); setOtpDemoCode(null); }}
                  className="mt-1 text-xs text-[var(--ink-soft)] hover:text-[var(--forest)]"
                >
                  Use a different number
                </button>
              </div>
            )}

            {otpError && <p className="text-sm text-[var(--clay-red)]">{otpError}</p>}

            <button
              type="submit"
              disabled={otpLoading || !phoneNumber || (otpSent && !otpCode)}
              className="w-full bg-[var(--forest)] px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60"
            >
              {otpLoading ? "Please wait…" : otpSent ? "Verify & sign in" : "Send one-time code"}
            </button>
          </form>
          )}

          {mode === "forgot" && (
            <div className="mt-6">
              <p className="text-sm text-[var(--ink-soft)]">
                We&apos;ll send a one-time code to your registered phone number — enter it below
                along with a new password.
              </p>
              <form onSubmit={resetSent ? submitReset : sendResetCode} className="mt-4 space-y-4">
                <div>
                  <label className="font-mono text-[11px] font-medium uppercase tracking-wide text-[var(--ink-soft)]">Phone number</label>
                  <input
                    value={resetPhone}
                    onChange={(e) => setResetPhone(e.target.value)}
                    placeholder="+233 XX XXX XXXX"
                    disabled={resetSent}
                    autoFocus
                    className="mt-1 w-full border-0 border-b-2 border-[var(--rule)] bg-transparent px-0 py-2 text-sm outline-none focus:border-[var(--forest)] disabled:text-[var(--ink-soft)]"
                  />
                </div>

                {resetSent && (
                  <>
                    <div>
                      <label className="font-mono text-[11px] font-medium uppercase tracking-wide text-[var(--ink-soft)]">One-time code</label>
                      <input
                        value={resetCode}
                        onChange={(e) => setResetCode(e.target.value)}
                        placeholder="6-digit code"
                        autoFocus
                        className="mt-1 w-full border-0 border-b-2 border-[var(--rule)] bg-transparent px-0 py-2 text-sm outline-none focus:border-[var(--forest)]"
                      />
                      {resetDemoCode && (
                        <p className="mt-2 rounded-sm border border-dashed border-[var(--gold)] bg-[var(--gold)]/10 px-3 py-2 text-xs text-[var(--ink)]">
                          SMS delivery isn&apos;t configured yet, so your code (<strong className="font-mono">{resetDemoCode}</strong>) has been filled in above automatically.
                        </p>
                      )}
                    </div>
                    <div>
                      <label className="font-mono text-[11px] font-medium uppercase tracking-wide text-[var(--ink-soft)]">New password</label>
                      <input
                        type="password"
                        value={resetNewPassword}
                        onChange={(e) => setResetNewPassword(e.target.value)}
                        placeholder="At least 8 characters"
                        className="mt-1 w-full border-0 border-b-2 border-[var(--rule)] bg-transparent px-0 py-2 text-sm outline-none focus:border-[var(--forest)]"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={() => { setResetSent(false); setResetCode(""); setResetError(null); }}
                      className="text-xs text-[var(--ink-soft)] hover:text-[var(--forest)]"
                    >
                      Use a different number
                    </button>
                  </>
                )}

                {resetError && <p className="text-sm text-[var(--clay-red)]">{resetError}</p>}
                {resetDone && <p className="text-sm" style={{ color: "var(--forest)" }}>Password reset — signing you in…</p>}

                <button
                  type="submit"
                  disabled={resetLoading || !resetPhone || (resetSent && (!resetCode || resetNewPassword.length < 8))}
                  className="w-full bg-[var(--forest)] px-4 py-2.5 text-sm font-medium text-white disabled:opacity-60"
                >
                  {resetLoading ? "Please wait…" : resetSent ? "Reset password & sign in" : "Send reset code"}
                </button>
              </form>
              <button
                type="button"
                onClick={() => { setMode("password"); setResetSent(false); setResetError(null); }}
                className="mt-4 text-xs text-[var(--ink-soft)] hover:text-[var(--forest)]"
              >
                ← Back to sign in
              </button>
            </div>
          )}

          <p className="mt-6 text-xs text-[var(--ink-soft)]">
            Which community you belong to is decided by your account, not chosen here — your
            administrator sets that up when your login is created.
          </p>
        </div>

        <div className="border border-dashed border-[var(--violet)] p-8" style={{ backgroundColor: "var(--violet-soft)" }}>
          <p className="font-mono text-[11px] font-medium uppercase tracking-[0.2em]" style={{ color: "var(--violet)" }}>
            Try it instantly
          </p>
          <h2 className="font-display mt-1 text-2xl" style={{ color: "var(--violet)" }}>
            Live demo — every dashboard
          </h2>
          <p className="mt-2 text-sm text-[var(--ink-soft)]">
            No account needed. Pick a role to see exactly what that person sees — real
            demo data, a real family, a real funeral in progress.
          </p>

          {demoError && <p className="mt-3 text-sm text-[var(--clay-red)]">{demoError}</p>}

          <div className="mt-4 grid grid-cols-2 gap-2">
            {DEMO_ROLES.map((r) => (
              <button
                key={r.value}
                onClick={() => tryDemo(r.value)}
                disabled={demoRole !== null}
                className="border border-[var(--rule)] bg-white px-3 py-2 text-left text-xs font-medium hover:border-[var(--violet)] hover:text-[var(--violet)] disabled:opacity-60"
              >
                {demoRole === r.value ? "Loading…" : r.label}
              </button>
            ))}
          </div>
        </div>
      </div>
      </div>
    </div>
  );
}
