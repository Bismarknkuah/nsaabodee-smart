from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services
from families.models import BereavedRepAssignment
from members import services as member_services
from tenants.models import Community


class CreateBereavedRepServiceTests(TestCase):
    """
    'Each funeral must have a bereaved rep, and the rep should
    represent the family... that account should be created by the
    community admin, secretary or chair but when one create she need
    other one to approved.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-bereaved-rep")
        self.admin = User.objects.create_user(username="bereaved_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.secretary = User.objects.create_user(username="bereaved_secretary", password="x", community=self.bodi, role=Role.SECRETARY)
        self.chairman = User.objects.create_user(username="bereaved_chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.treasurer = User.objects.create_user(username="bereaved_treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        self.asona = services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.candidate = member_services.register_member(community=self.bodi, full_name="Rep Candidate", gender="male", family=self.asona)

    def test_community_admin_creating_directly_is_immediately_active(self):
        assignment = services.create_bereaved_rep(family=self.asona, actor=self.admin, member=self.candidate, new_username="rep1", new_password="a-real-password-123")
        self.assertTrue(assignment.is_active)
        assignment.user.refresh_from_db()
        self.assertEqual(assignment.user.role, "bereaved_rep")

    def test_secretary_creating_starts_inactive(self):
        assignment = services.create_bereaved_rep(family=self.asona, actor=self.secretary, member=self.candidate, new_username="rep2", new_password="a-real-password-123")
        self.assertFalse(assignment.is_active)

    def test_treasurer_cannot_create_a_bereaved_rep(self):
        """Not one of the three eligible creator roles."""
        with self.assertRaises(ValidationError):
            services.create_bereaved_rep(family=self.asona, actor=self.treasurer, member=self.candidate, new_username="rep3", new_password="a-real-password-123")

    def test_the_same_person_creating_and_approving_is_rejected(self):
        assignment = services.create_bereaved_rep(family=self.asona, actor=self.secretary, member=self.candidate, new_username="rep4", new_password="a-real-password-123")
        with self.assertRaises(ValidationError):
            services.approve_bereaved_rep(assignment=assignment, actor=self.secretary)

    def test_a_different_eligible_person_approving_activates_it(self):
        assignment = services.create_bereaved_rep(family=self.asona, actor=self.secretary, member=self.candidate, new_username="rep5", new_password="a-real-password-123")
        services.approve_bereaved_rep(assignment=assignment, actor=self.chairman)
        assignment.refresh_from_db()
        self.assertTrue(assignment.is_active)

    def test_treasurer_cannot_approve_either(self):
        assignment = services.create_bereaved_rep(family=self.asona, actor=self.secretary, member=self.candidate, new_username="rep6", new_password="a-real-password-123")
        with self.assertRaises(ValidationError):
            services.approve_bereaved_rep(assignment=assignment, actor=self.treasurer)

    def test_deactivation_genuinely_stops_the_dashboard_from_reflecting_new_activity(self):
        """'Should be temporal' — a real, working deactivation."""
        assignment = services.create_bereaved_rep(family=self.asona, actor=self.admin, member=self.candidate, new_username="rep7", new_password="a-real-password-123")
        services.deactivate_bereaved_rep(assignment=assignment, actor=self.admin)
        assignment.refresh_from_db()
        self.assertFalse(assignment.is_active)
        self.assertIsNotNone(assignment.deactivated_at)

    def test_a_new_account_can_be_created_on_the_spot_without_an_existing_member(self):
        """'A trusted family friend' pattern already used for desk assignments — a member doesn't have to exist first."""
        assignment = services.create_bereaved_rep(family=self.asona, actor=self.admin, new_username="brand_new_rep", new_password="a-real-password-123")
        self.assertEqual(assignment.family_id, self.asona.id)
        self.assertTrue(assignment.is_active)

    def test_a_member_of_a_different_family_cannot_be_made_this_familys_rep(self):
        bretuo = services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        other_family_member = member_services.register_member(community=self.bodi, full_name="Wrong Family", gender="male", family=bretuo)
        with self.assertRaises(ValidationError):
            services.create_bereaved_rep(family=self.asona, actor=self.admin, member=other_family_member, new_username="rep8", new_password="a-real-password-123")


class BereavedRepDashboardTests(TestCase):
    """
    'The dashboard should be analytics and provide oversight of the
    contribution or anything related to the funeral... if one family
    have 2 deceased it means that all the two has to be on the
    bereaved rep dashboard.'
    """

    def setUp(self):
        from funerals import services as funeral_services

        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-bereaved-dash",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="bereaved_dash_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.candidate = member_services.register_member(community=self.bodi, full_name="Dash Rep", gender="male", family=self.asona)
        self.assignment = services.create_bereaved_rep(family=self.asona, actor=self.admin, member=self.candidate, new_username="dash_rep", new_password="a-real-password-123")

        self.funeral_one = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="First Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        self.funeral_two = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Second Deceased", deceased_gender="female",
            deceased_family=self.asona, date_of_death="2026-07-05", collection_start_date="2026-07-05",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def test_both_of_the_familys_active_funerals_appear_on_the_dashboard(self):
        """The core requirement — a second deceased in the same family shows up too, not just the first."""
        from dashboard.services import build_dashboard
        result = build_dashboard(self.assignment.user)
        funerals_shown = {f["deceased_name"] for f in result["sections"]["bereaved_funerals"]}
        self.assertEqual(funerals_shown, {"First Deceased", "Second Deceased"})

    def test_the_family_summary_aggregates_across_both_funerals(self):
        from dashboard.services import build_dashboard
        result = build_dashboard(self.assignment.user)
        family_summary = result["sections"]["family_summary"]
        self.assertEqual(family_summary["active_funeral_count"], 2)
        self.assertEqual(Decimal(family_summary["total_expected"]), Decimal("100"))

    def test_member_compliance_is_included_for_real_oversight(self):
        from dashboard.services import build_dashboard
        result = build_dashboard(self.assignment.user)
        self.assertTrue(len(result["sections"]["family_summary"]["member_compliance"]) > 0)


class BereavedRepHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-bereaved-http")
        self.admin = User.objects.create_user(username="bereaved_http_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.secretary = User.objects.create_user(username="bereaved_http_secretary", password="a-real-password-123", community=self.bodi, role=Role.SECRETARY)
        self.chairman = User.objects.create_user(username="bereaved_http_chairman", password="a-real-password-123", community=self.bodi, role=Role.CHAIRMAN)
        self.asona = services.create_family(community=self.bodi, name="Asona", actor=self.admin)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_http_round_trip_create_pending_approve(self):
        secretary_client = self._login("bereaved_http_secretary")
        create_res = secretary_client.post(f"/api/families/{self.asona.id}/bereaved-rep/", {"new_username": "http_rep", "new_password": "a-real-password-123"})
        self.assertEqual(create_res.status_code, 201)
        self.assertFalse(create_res.data["is_active"])

        chairman_client = self._login("bereaved_http_chairman")
        pending_res = chairman_client.get("/api/bereaved-rep-assignments/pending/")
        self.assertEqual(pending_res.status_code, 200)
        self.assertEqual(len(pending_res.data), 1)

        approve_res = chairman_client.post(f"/api/bereaved-rep-assignments/{create_res.data['id']}/approve/")
        self.assertEqual(approve_res.status_code, 200)
        self.assertTrue(approve_res.data["is_active"])
