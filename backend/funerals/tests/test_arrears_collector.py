from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import ContributionObligation, FuneralEvent
from members import services as member_services
from tenants.models import Community


class ArrearsCollectorRoleTests(TestCase):
    """'We will have two type of collectors, one collect on going funerals and the other one is arrears collector who collect arrears payment.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="acr-bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="acr_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.arrears_collector = User.objects.create_user(username="acr_arrears_collector", password="a-real-password-123", community=self.bodi, role=Role.ARREARS_COLLECTOR)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)

        self.old_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Old Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2025-01-01", collection_start_date="2025-01-01",
        )
        self.old_funeral.status = FuneralEvent.Status.CLOSED
        self.old_funeral.save(update_fields=["status"])
        self.old_obligation = ContributionObligation.objects.get(funeral_event=self.old_funeral, member=self.member)

    def test_an_arrears_collector_can_record_a_payment_against_a_closed_funerals_obligation(self):
        payment = funeral_services.record_payment(
            obligation=self.old_obligation, amount=Decimal("50"), method="cash",
            collector=self.arrears_collector, collector_name="Arrears Collector",
        )
        self.assertEqual(payment.amount, Decimal("50"))
        self.old_obligation.refresh_from_db()
        self.assertEqual(self.old_obligation.balance, Decimal("0"))

    def test_an_arrears_collector_can_record_a_payment_over_http(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "acr_arrears_collector", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(
            f"/api/funerals/{self.old_funeral.id}/obligations/{self.old_obligation.id}/record-payment/",
            {"amount": "50", "method": "cash", "collector_name": "Arrears Collector"},
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)

    def test_arrears_collector_is_manageable_by_the_community_admin(self):
        from accounts.permissions import can_restrict_features_for
        self.assertTrue(can_restrict_features_for(self.admin, self.arrears_collector))


class MemberArrearsLookupTests(TestCase):
    """'Their arrears they own should show.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="mal-bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="mal_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.arrears_collector = User.objects.create_user(username="mal_arrears_collector", password="a-real-password-123", community=self.bodi, role=Role.ARREARS_COLLECTOR)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)

        self.old_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Old Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2025-01-01", collection_start_date="2025-01-01",
        )
        self.old_funeral.status = FuneralEvent.Status.CLOSED
        self.old_funeral.save(update_fields=["status"])

    def test_an_unpaid_closed_funeral_obligation_shows_as_arrears(self):
        arrears = funeral_services.lookup_member_arrears(member=self.member)
        self.assertEqual(len(arrears), 1)
        self.assertEqual(arrears[0].funeral_event, self.old_funeral)

    def test_a_fully_paid_obligation_does_not_show_as_arrears(self):
        obligation = ContributionObligation.objects.get(funeral_event=self.old_funeral, member=self.member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("50"), method="cash", collector_name="Test")
        arrears = funeral_services.lookup_member_arrears(member=self.member)
        self.assertEqual(len(arrears), 0)

    def test_arrears_are_returned_oldest_funeral_first(self):
        newer_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Newer Deceased", deceased_gender="female",
            deceased_family=self.asona, date_of_death="2025-06-01", collection_start_date="2025-06-01",
        )
        newer_funeral.status = FuneralEvent.Status.CLOSED
        newer_funeral.save(update_fields=["status"])
        arrears = funeral_services.lookup_member_arrears(member=self.member)
        self.assertEqual(len(arrears), 2)
        self.assertEqual(arrears[0].funeral_event, self.old_funeral)
        self.assertEqual(arrears[1].funeral_event, newer_funeral)

    def test_arrears_lookup_over_http_includes_funeral_name_and_status(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "mal_arrears_collector", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get(f"/api/members/{self.member.id}/arrears/")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["member_name"], "Kojo")
        self.assertEqual(len(res.data["arrears"]), 1)
        self.assertEqual(res.data["arrears"][0]["funeral_deceased_name"], "Old Deceased")
        self.assertEqual(res.data["arrears"][0]["funeral_status"], "closed")

    def test_a_different_communitys_arrears_collector_cannot_look_up_this_member(self):
        other_community = Community.objects.create(name="Other Town", slug="mal-other")
        other_collector = User.objects.create_user(username="mal_other_collector", password="a-real-password-123", community=other_community, role=Role.ARREARS_COLLECTOR)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "mal_other_collector", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.get(f"/api/members/{self.member.id}/arrears/")
        self.assertEqual(res.status_code, 404)
