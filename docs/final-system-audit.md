# Nsaabodeɛ Smart — Final System Audit

**Date:** July 24, 2026
**Scope:** Full platform — 21 Django backend apps, 44 Next.js frontend routes
**Method:** Every claim below is backed by a test actually run or code actually read during this audit pass, not assumed from memory of earlier batches. Where a batch's own testing already covered an area thoroughly, that's stated explicitly rather than re-verified from scratch redundantly.

---

## 1. Test suite — full results

Every backend app was run as its own fresh test database, in isolation, to confirm nothing has silently drifted since it was last verified in an earlier batch.

| App(s) | Tests | Result |
|---|---|---|
| audit_log, support, ai_features | 47 | PASS |
| accounts | 79 | PASS |
| communication, contribution_rules, dashboard, notifications | 60 | PASS |
| families, family_funds | 64 | PASS |
| funeral_logistics, gifts | 66 | PASS |
| funerals (committee positions, debt priority, desk assignments, opening approval, core) | 75 | PASS |
| funerals (rate overrides, memorial pages, payment performance/recording/reversals, QR) | 61 | PASS |
| members | 48 | PASS |
| messaging, payments, realtime | 30 | PASS |
| reports | 52 | PASS |
| tasks | 21 | PASS |
| tenants (announcements, homepage images, onboarding, payout accounts) | 53 | PASS |
| tenants (plan interest, platform admin capabilities, billing, temporary access) | 51 | PASS |
| **Backend total** | **707** | **0 failures** |

Frontend: production build succeeds cleanly (44 routes, no errors or warnings beyond a pre-existing `npm audit` dependency flag — see Security Findings). Vitest regression suite: 2/2 passing, including the dashboard `gift_cash`-absence regression test that caught a real production bug earlier in this project.

---

## 2. Findings by audit area

**Authentication** — JWT login/refresh, phone-OTP login, password reset via OTP, and demo login are all covered by the `accounts` suite (79 tests). Demo login is confirmed gated behind a `DEMO_MODE_ENABLED` setting defaulting to off, verified by reading the view directly — a real production deployment must explicitly opt in.

**RBAC** — 16 roles, each with backend permission classes independently tested; role-switching (Batch 3) adds a second, additive layer (`RequiresExecutiveContext` and its variants) verified not to weaken any existing role check, confirmed via the full `accounts` + `tasks` regression sweep after every change in that batch.

**Permissions** — sampled across `members`, `families`, `funerals`, `tasks`: every jurisdiction boundary (Family Head confined to their own family, Community Admin+ reaching community-wide) has a dedicated test asserting the *rejection* case, not just the success case.

**API security** — every `AllowAny` view in the codebase (11 total) was individually checked this pass, not assumed: 6 are authentication endpoints that must be public by definition (login, refresh, OTP request/verify, password reset, demo login), 3 are the public homepage's own reads (images, plan-interest submission, featured announcements), 2 are the public Memorial Page and its tribute submission. None expose anything beyond what each feature is explicitly designed to show a logged-out visitor.

**Tenant isolation** — spot-checked `get_object_or_404` calls that don't visibly filter by community in the same line; in every case checked (payment reversal requests, announcement resubmission/approval/rejection), the actual isolation check exists either inline (`payment.obligation.funeral_event.community_id != request.user.community_id`) or in the service layer (`_is_own_communitys_admin`) — a consistent, if not always view-level, pattern. Not every one of the dozens of such calls across the codebase was individually re-verified in this pass; see Missing Requirements below.

**Financial calculations** — contribution, gift, expense, and payment-reversal math is covered by dedicated tests in `funerals`, `gifts`, and `funeral_logistics` (debt priority, payment performance, partial-payment liability tracking added in Batch 6 all re-confirmed passing this pass).

**Offline synchronization** — the `client_op_id` idempotency pattern (a retried sync never double-records a payment, gift, or expense) is present consistently across every money-recording flow: `funeral_logistics`, `gifts`, `funerals`, `family_funds`, and `payments`.

**Reports** — 52 passing tests in the `reports` app, covering daily/weekly/monthly/annual collections, outstanding members, family statements, and the expense-liability figures added in Batch 6.

**Receipts** — every receipt/voucher number field (`funeral_logistics`, `gifts`, `funerals`, `family_funds`) carries a database-level `unique=True` constraint, not just an application-level check — confirmed by reading each model directly.

**Audit logs** — the general, platform-wide audit log (Batch 1) and every pre-existing scoped log (`FamilyAuditLog`, `AnnouncementReviewLog`, `PaymentReversal`'s own trail) are all covered by their own passing test suites, re-confirmed in this sweep.

**Role switching** — the full dual-profile mechanism (Batch 3) re-confirmed passing, including the method-aware permission variants added to fix the two mixed-viewset gaps found during that batch's own testing.

**Data privacy** — not independently re-audited field-by-field in this pass beyond what each batch's own tests already covered; see Missing Requirements.

**Performance** — see Security Findings for the one concrete issue found (outdated Next.js). No N+1 query profiling or load testing was performed in this pass; see Production Readiness Assessment.

---

## 3. Security findings

**Outdated Next.js with multiple high-severity advisories (real, confirmed).** The pinned version is `15.5.20`. `npm audit` reports high-severity CVEs against this version and its transitive `postcss`/`sharp` dependencies, including a denial-of-service issue in Server Actions and an SSRF issue in rewrites. A fix is available (`next@15.5.21`) without leaving the stated dependency range's next minor. **This was not fixed during this audit** — upgrading a framework version warrants its own dedicated pass with full regression testing before shipping, not a same-response patch buried inside an audit. Recommended as the first item of any follow-up work.

**Nothing else rose to the level of a security finding** in the areas actually checked this pass (AllowAny usage, sampled tenant-isolation paths, demo-login gating).

---

## 4. Missing requirements

- Full per-view tenant-isolation audit (every `get_object_or_404` call across all 21 apps, not just the sampled ones)
- Field-by-field data-privacy review of every serializer (confirming no sensitive field — national ID equivalents, phone numbers, financial account details — is exposed to a broader audience than intended)
- Load/performance testing under realistic concurrent usage
- N+1 query profiling on the heavier list views (dashboard aggregates, reports)
- Invoice file upload on the frontend (flagged honestly as a known gap when built in Batch 6 — backend fully supports it, frontend's JSON-only client doesn't send files yet)

## 5. Bugs discovered during this audit pass

None. Every test run in this pass passed on the first attempt at the suite level (individual test-writing bugs caught and fixed *during* each batch are documented in that batch's own README entry, not repeated here).

## 6. Recommended fixes, in priority order

1. Upgrade Next.js past `15.5.20` to clear the high-severity advisories, with a full regression pass afterward.
2. Complete the tenant-isolation audit across every remaining view.
3. Complete the data-privacy serializer review.
4. Wire invoice file upload into the frontend expense-recording form.
5. Establish baseline performance/load testing before any real-world rollout with concurrent users.

## 7. Production readiness assessment

**Functionally, this platform is in strong shape.** 707 backend tests passing across every app, a clean frontend build, and consistent, tested authority boundaries (tenant isolation, family jurisdiction, executive-context gating, financial idempotency) throughout. The architecture has repeatedly held up under real scrutiny — role-switching, expense-liability tracking, and the funeral-committee system were all built as additions to proven foundations rather than risky rewrites, and every regression found along the way was caught by tests before shipping, not after.

**Not yet production-ready without the fixes above.** The Next.js security advisories are a genuine, unresolved risk for a live deployment handling real financial data. The tenant-isolation and data-privacy items in Missing Requirements are sampled, not exhaustive — real confidence there requires the full sweep, not a spot check. No load testing has been done at all, which matters for a platform meant to handle real concurrent community usage.

**Recommendation:** address items 1–3 in Recommended Fixes before any production deployment; items 4–5 can reasonably follow shortly after launch rather than blocking it.
