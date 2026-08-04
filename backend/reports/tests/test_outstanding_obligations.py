from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from members import services as member_services
from reports import services
from tenants.models import Community


class MemberOutstandingObligationsTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)
        self.member_user = User.objects.create_user(username="kojo_login", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.member, user=self.member_user, actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def test_service_returns_the_real_obligation_with_a_payable_id(self):
        result = services.member_outstanding_obligations(self.member)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["deceased_name"], "Yaw Asona")
        self.assertEqual(Decimal(result[0]["balance"]), Decimal("50"))

    def test_paid_obligation_disappears_from_the_list(self):
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash")
        result = services.member_outstanding_obligations(self.member)
        self.assertEqual(len(result), 0)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_member_can_see_their_own_outstanding_obligations(self):
        client = self._login("kojo_login")
        res = client.get("/api/my-obligations/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["obligation_id"], str(
            __import__("funerals.models", fromlist=["ContributionObligation"]).ContributionObligation.objects.get(
                funeral_event=self.funeral, member=self.member
            ).id
        ))

    def test_user_without_a_linked_member_gets_an_empty_list_not_an_error(self):
        User.objects.create_user(username="no_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        client = self._login("no_member")
        res = client.get("/api/my-obligations/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, [])

    def test_collector_can_look_up_another_members_obligations_at_the_front_desk(self):
        collector = User.objects.create_user(username="collector1", password="x", community=self.bodi, role=Role.COLLECTOR)
        client = self._login("collector1")
        res = client.get(f"/api/reports/members/{self.member.id}/outstanding-obligations/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

    def test_ordinary_community_member_cannot_look_up_someone_elses_obligations(self):
        other_member_user = User.objects.create_user(username="another_member", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        client = self._login("another_member")
        res = client.get(f"/api/reports/members/{self.member.id}/outstanding-obligations/")
        self.assertEqual(res.status_code, 403)
