"""
The executable role model — "make sure every role has all the features it
needs and is restricted from the features its role type does not have."

One user per role, every protected area hit by every role, and an explicit
allowed-set per area. If a role reaches something it should not, or is
refused something it needs, this fails and names both the role and the
area. Enforced at the backend, where it actually matters — the sidebar only
hides links.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from dashboard.services import build_dashboard
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from tenants.models import Community

ALL = set(Role.values)
FAMILY_ROLES = {"family_head", "family_secretary", "family_treasurer", "family_registration_officer", "family_arrears_officer"}


class RoleAccessMatrixTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="ram-bodi", default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"), default_town_leader_amount=Decimal("20"))
        admin = User.objects.create_user(username="ram_seed_admin", password="x", community=cls.bodi, role=Role.COMMUNITY_ADMIN)
        cls.asona = family_services.create_family(community=cls.bodi, name="Asona", actor=admin)
        cls.bretuo = family_services.create_family(community=cls.bodi, name="Bretuo", actor=admin)
        for fam in (cls.asona, cls.bretuo):
            family_services.recommend_family_rate(family=fam, amount=Decimal("50"), actor=admin)
            family_services.approve_family_rate(family=fam, actor=admin)

        cls.users = {}
        for role in ALL:
            community = None if role == "platform_admin" else cls.bodi
            user = User.objects.create_user(username=f"ram_{role}", password="x", community=community, role=role)
            if role in FAMILY_ROLES or role in ("community_member", "bereaved_rep", "collector", "arrears_collector"):
                member = member_services.register_member(community=cls.bodi, full_name=f"Member {role}", gender="male", family=cls.asona)
                member_services.link_member_to_user(member=member, user=user, actor=admin)
            cls.users[role] = user

        # A member who owes on a CLOSED funeral (arrears), then an OPEN funeral.
        cls.debtor = member_services.register_member(community=cls.bodi, full_name="Debtor", gender="male", family=cls.asona)
        closed = funeral_services.create_funeral_event(community=cls.bodi, deceased_name="Closed One", deceased_gender="female", deceased_family=cls.bretuo, date_of_death="2026-01-01", collection_start_date="2026-01-02")
        cls.closed_obligation = closed.obligations.get(member=cls.debtor)
        funeral_services.close_funeral_event(funeral=closed, actor=admin)
        cls.closed_funeral = closed
        # A member with NO arrears, so an open-funeral payment isn't blocked by the older-debt rule.
        cls.clean = member_services.register_member(community=cls.bodi, full_name="Clean Payer", gender="female", family=cls.asona)
        cls.open_funeral = funeral_services.create_funeral_event(community=cls.bodi, deceased_name="Open One", deceased_gender="male", deceased_family=cls.bretuo, date_of_death="2026-09-01", collection_start_date="2026-09-02")
        cls.open_obligation = cls.open_funeral.obligations.get(member=cls.clean)

    def _client(self, role):
        c = APIClient(); c.force_authenticate(self.users[role]); return c

    def _assert_matrix(self, area, allowed, request_fn, ok=(200, 201)):
        wrong = []
        for role in sorted(ALL):
            status_code = request_fn(self._client(role)).status_code
            reached = status_code in ok
            if reached and role not in allowed:
                wrong.append(f"{role} REACHED {area} ({status_code}) but must not")
            if not reached and role in allowed:
                wrong.append(f"{role} was REFUSED {area} ({status_code}) but needs it")
        self.assertFalse(wrong, "\n" + "\n".join(wrong))

    # ---------------- read areas ----------------

    def test_member_registry_analytics(self):
        self._assert_matrix(
            "member registry analytics",
            allowed={"community_admin", "chairman", "secretary", "community_registration_desk", "town_registration_officer", "traditional_leader"} | FAMILY_ROLES,
            request_fn=lambda c: c.get("/api/members/registry-analytics/"),
        )

    def test_town_elders_ledger(self):
        self._assert_matrix(
            "Town Elders ledger",
            allowed={"traditional_leader", "community_admin", "chairman", "secretary", "town_elders_arrears_officer"},
            request_fn=lambda c: c.get("/api/reports/town-elders-ledger/"),
        )

    def test_arrears_worklist(self):
        self._assert_matrix(
            "community arrears worklist",
            allowed={"arrears_collector", "community_admin", "treasurer", "financial_secretary"},
            request_fn=lambda c: c.get("/api/arrears/worklist/"),
        )

    def test_daily_collections_report(self):
        self._assert_matrix(
            "daily collections report",
            allowed={"community_admin", "traditional_leader", "chairman", "secretary", "treasurer", "financial_secretary", "auditor"},
            request_fn=lambda c: c.get("/api/reports/collections/daily/"),
        )

    def test_community_liabilities(self):
        self._assert_matrix(
            "community expense liabilities",
            # Recorders plus the two who oversee spending without recording it (the same five the sidebar's Liabilities link already shows).
            allowed={"community_admin", "chairman", "treasurer", "financial_secretary", "auditor"},
            request_fn=lambda c: c.get("/api/expenses/liabilities/"),
        )

    def test_a_funerals_expense_ledger_is_oversight_only(self):
        """Reading what was spent is for the recorders plus the Chairman and Auditor — never every logged-in member."""
        self._assert_matrix(
            "funeral expense ledger (read)",
            allowed={"community_admin", "chairman", "treasurer", "financial_secretary", "auditor"},
            request_fn=lambda c: c.get(f"/api/funerals/{self.open_funeral.id}/expenses/"),
        )

    def test_recording_an_expense_is_narrower_than_reading_one(self):
        self._assert_matrix(
            "record a funeral expense",
            allowed={"community_admin", "treasurer", "financial_secretary"},
            request_fn=lambda c: c.post(f"/api/funerals/{self.open_funeral.id}/expenses/", {"description": "Chairs", "category": "venue", "incurred_on": "2026-09-02", "amount": "10"}),
            ok=(200, 201),
        )

    def test_manageable_users(self):
        self._assert_matrix(
            "user management list",
            allowed={"community_admin", "chairman", "family_head", "family_secretary", "traditional_leader"},
            request_fn=lambda c: c.get("/api/accounts/manageable-users/"),
        )

    def test_subscription_plans_are_platform_admin_only(self):
        self._assert_matrix("subscription plans", allowed={"platform_admin"}, request_fn=lambda c: c.get("/api/tenants/subscription-plans/"))

    def test_the_platform_community_console_is_platform_admin_only(self):
        """The Community Admin runs one community; the console that lists and bills every community is the platform's."""
        self._assert_matrix("platform community console", allowed={"platform_admin"}, request_fn=lambda c: c.get("/api/tenants/communities/"))

    def test_audit_log(self):
        self._assert_matrix("audit log", allowed={"platform_admin", "community_admin"}, request_fn=lambda c: c.get("/api/audit-log/"))

    # ---------------- write areas ----------------

    def test_record_payment_on_an_open_funeral(self):
        self._assert_matrix(
            "record payment (open funeral)",
            allowed={"collector", "arrears_collector", "community_admin"},
            request_fn=lambda c: c.post(f"/api/funerals/{self.open_funeral.id}/obligations/{self.open_obligation.id}/record-payment/", {"amount": "1", "method": "cash", "collector_name": "M"}),
        )

    def test_record_payment_on_a_closed_funeral_is_arrears_only(self):
        self._assert_matrix(
            "record payment (closed funeral = arrears)",
            # The debtor is in Asona, so Asona's own Family Arrears Officer is in scope; the Town Elders one is not (the debtor is no elder).
            allowed={"arrears_collector", "community_admin", "family_arrears_officer"},
            request_fn=lambda c: c.post(f"/api/funerals/{self.closed_funeral.id}/obligations/{self.closed_obligation.id}/record-payment/", {"amount": "1", "method": "cash", "collector_name": "M"}),
        )

    def test_register_a_member(self):
        # Town Registration Officer may only register Town Elders (posting an ordinary member is refused),
        # and the Family Head reviews rather than enters data — neither reaches 201 here.
        self._assert_matrix(
            "register an ordinary member",
            allowed={"community_admin", "chairman", "secretary", "collector", "family_secretary", "family_registration_officer", "community_registration_desk"},
            request_fn=lambda c: c.post("/api/members/", {"full_name": "New Person", "gender": "male", "family_id": str(self.asona.id)}),
            ok=(201,),
        )

    # ---------------- dashboards ----------------

    def test_every_role_lands_on_exactly_its_own_dashboard_section(self):
        expected = {
            "platform_admin": "platform_overview",
            "community_admin": "community_overview", "chairman": "community_overview", "secretary": "community_overview",
            "traditional_leader": "traditional_leader_overview", "town_elders_arrears_officer": "traditional_leader_overview",
            "treasurer": "financial_overview", "financial_secretary": "financial_overview", "auditor": "financial_overview",
            "collector": "collector_performance", "arrears_collector": "arrears_collector_overview",
            "family_arrears_officer": "family_arrears_officer_performance",
            "family_head": "family_overview", "family_secretary": "family_overview", "family_treasurer": "family_overview",
            "town_registration_officer": "registration_overview", "community_registration_desk": "registration_overview", "family_registration_officer": "registration_overview",
        }
        wrong = []
        for role in sorted(ALL):
            sections = list(build_dashboard(self.users[role])["sections"])
            if role in expected and sections != [expected[role]]:
                wrong.append(f"{role}: got {sections}, expected [{expected[role]}]")
            if role not in expected and any(k in ("community_overview", "financial_overview", "collector_performance", "traditional_leader_overview", "platform_overview") for k in sections):
                wrong.append(f"{role}: got a management/financial section {sections}")
        self.assertFalse(wrong, "\n" + "\n".join(wrong))
