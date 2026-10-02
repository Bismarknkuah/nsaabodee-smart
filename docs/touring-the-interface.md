# Touring the Interface

Once `Install-Nsaabodee.bat` (or `docker compose up`) has finished and
your browser opened to `http://localhost:3000`, here's what's actually
there to look at — grounded in the real demo data the system seeds for
you, not a made-up tour.

## Logging in

Every demo account uses the same password:

```
demo-password-not-for-real-use
```

Usernames follow the pattern `demo_<role>` — for example
`demo_community_admin`, `demo_chairman`, `demo_family_head`. The full
list is below. All demo accounts live in one seeded "Demo Community"
with two families (**Asona** and **Bretuo**), a funeral already in
progress ("Demo Deceased," opened yesterday), a real contribution
payment, a real gift, a Family Fund with one contribution, and one
assigned task — so every dashboard shows real numbers immediately, not
an empty shell.

## What each login actually shows

| Username | What their dashboard is built around |
|---|---|
| `demo_super_admin` | Cross-community — no single Member profile. Visit **Communities** in the top nav: this is the platform-admin console for creating, editing, and deactivating entire communities (not just this Demo one). |
| `demo_platform_admin` | Same as Super Admin — the Communities console, platform-wide. |
| `demo_community_admin` | The full community-wide picture: every family, every funeral, every ledger, with nothing hidden. This is also the account that can adjust general and tiered contribution rates on the **Contribution Rules** page, and the one you'd use to open **Families**, **Members**, and **Funerals** and see everything in them. |
| `demo_chairman` | Community-wide financial overview, plus the authority to approve a funeral opening (see below) and adjust contribution rates — the same tier as Community Admin for those specific actions. |
| `demo_secretary` | Same approval/rate-setting authority as Chairman, plus general community oversight. |
| `demo_treasurer` | A financial breakdown of the community's mandatory ledgers — deliberately **without** gift/donation totals, which are private to the family and Community Admin. Log in as this account specifically to see that restriction in action. |
| `demo_financial_secretary` | Same financial-breakdown view as Treasurer. |
| `demo_auditor` | Same financial-breakdown view, read-oriented. |
| `demo_collector` | Their own collection performance — how much they personally have recorded, tied to the one real payment already seeded. Try the **Front Desk** page with this account to see the actual "search a member, see what they owe, take a payment" flow. |
| `demo_family_head` | This is the **Asona family's own head** — their dashboard shows Asona's family statement in full (including gift/donation detail, which committee roles don't see). Try the **Funerals** page's "Request an opening" button and the per-member rate override panel — both are scoped to exactly this family. |
| `demo_family_secretary` | Same family-scoped view and authority as Family Head for Asona (registering members, assigning tasks, setting rate overrides — everything except being *the* head). |
| `demo_family_treasurer` | Asona's family financial view, plus Family Fund approval authority — check the Family Fund page to see the one seeded contribution. |
| `demo_community_member` | The self-service, member-facing side of the app: **My Receipts**, **My Donations Received**, and — since this demo member has a real assigned task and a family with an open funeral — the dashboard's task and obligation cards actually populate. Log in as this account to see the "Pay via MoMo" prompt on a real outstanding balance. |
| `demo_guest` | Deliberately the most limited view — public information about the active funeral only, no financial breakdown at all. Useful for confirming the platform's privacy boundaries actually hold. |
| `demo_bereaved_rep` | A family-facing financial overview for Asona's active funeral specifically. |
| `demo_notification_officer` | Delivery-attempt totals by status (sent/failed/pending) — the operational view for whoever's responsible for the SMS/WhatsApp/email layer actually reaching people. |

## Things worth deliberately trying

- **Front Desk** (`demo_collector` or `demo_community_admin`): search
  "Demo", find a member, see their real outstanding balance, and record
  a payment. Try switching your laptop to airplane mode first — the
  form will tell you it's saving locally and will sync once you're
  back online.
- **Committee privacy** (`demo_treasurer` vs `demo_community_admin`):
  open the same funeral's ledger breakdown as each account and compare
  — the Treasurer's view has no gift/donation figures at all; the
  Admin's does.
- **The two-approval funeral workflow** (`demo_family_head`, then
  `demo_secretary`, then `demo_chairman`): as the Family Head, use
  "Request an opening" for a *new* funeral. Nobody gets billed yet.
  Log in as Secretary and approve — still nothing billed (only one
  approval so far). Log in as Chairman and approve — now it activates
  and bills everyone.
- **Desk assignments** (`demo_family_head`): on the Funerals page, open
  the seeded funeral and try "Assign someone to the funeral desk" — you
  can create a brand-new login for someone who isn't a registered
  member at all, purely to let them collect at your family's desk.
