from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services
from funerals.models import ArrearsCorrectionRequest, ContributionObligation, FuneralEvent
from members import services as member_services
from tenants.models import Community


class FamilyArrearsOfficerScopeTests(TestCase):
    """'Each family should also have family arrears officer.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="faos-bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="faos_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        family_services.recommend_family_rate(family=self.bretuo, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.bretuo, actor=self.admin)

        self.asona_officer = User.objects.create_user(username="faos_officer", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_ARREARS_OFFICER)
        officer_member = member_services.register_member(community=self.bodi, full_name="Officer Member", gender="male", family=self.asona)
        member_services.link_member_to_user(member=officer_member, user=self.asona_officer, actor=self.admin)

        self.asona_member = member_services.register_member(community=self.bodi, full_name="Asona Debtor", gender="male", family=self.asona)
        self.bretuo_member = member_services.register_member(community=self.bodi, full_name="Bretuo Debtor", gender="male", family=self.bretuo)

        from funerals import services as funeral_services
        self.old_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Old Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2025-01-01", collection_start_date="2025-01-01",
        )

    def test_a_family_arrears_officer_can_collect_from_their_own_familys_member(self):
        obligation = ContributionObligation.objects.get(funeral_event=self.old_funeral, member=self.asona_member)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "faos_officer", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(
            f"/api/funerals/{self.old_funeral.id}/obligations/{obligation.id}/record-payment/",
            {"amount": "50", "method": "cash", "collector_name": "Officer"},
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)

    def test_a_family_arrears_officer_cannot_collect_from_a_different_familys_member(self):
        obligation = ContributionObligation.objects.get(funeral_event=self.old_funeral, member=self.bretuo_member)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "faos_officer", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(
            f"/api/funerals/{self.old_funeral.id}/obligations/{obligation.id}/record-payment/",
            {"amount": "50", "method": "cash", "collector_name": "Officer"},
            format="json",
        )
        self.assertEqual(res.status_code, 403)


class TownEldersArrearsOfficerScopeTests(TestCase):
    """'The town elders should also have arrears.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="teao-bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="teao_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

        self.officer = User.objects.create_user(username="teao_officer", password="a-real-password-123", community=self.bodi, role=Role.TOWN_ELDERS_ARREARS_OFFICER)
        self.elder = member_services.register_member(community=self.bodi, full_name="An Elder", gender="male", family=self.asona, is_town_leader=True)
        self.ordinary_member = member_services.register_member(community=self.bodi, full_name="Ordinary Member", gender="male", family=self.asona)

        from funerals import services as funeral_services
        self.old_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Old Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2025-01-01", collection_start_date="2025-01-01",
        )

    def test_can_collect_from_a_town_elder(self):
        obligation = ContributionObligation.objects.get(funeral_event=self.old_funeral, member=self.elder)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "teao_officer", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(
            f"/api/funerals/{self.old_funeral.id}/obligations/{obligation.id}/record-payment/",
            {"amount": "50", "method": "cash", "collector_name": "Officer"},
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)

    def test_cannot_collect_from_an_ordinary_member(self):
        obligation = ContributionObligation.objects.get(funeral_event=self.old_funeral, member=self.ordinary_member)
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "teao_officer", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(
            f"/api/funerals/{self.old_funeral.id}/obligations/{obligation.id}/record-payment/",
            {"amount": "50", "method": "cash", "collector_name": "Officer"},
            format="json",
        )
        self.assertEqual(res.status_code, 403)


class ArrearsCorrectionWorkflowTests(TestCase):
    """'If they paid but the system didn't reflect, the arrears collector should edit but have to be approved by the community treasurer before it reflects.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="acw-bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="acw_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.treasurer = User.objects.create_user(username="acw_treasurer", password="a-real-password-123", community=self.bodi, role=Role.TREASURER)
        self.arrears_collector = User.objects.create_user(username="acw_arrears_collector", password="a-real-password-123", community=self.bodi, role=Role.ARREARS_COLLECTOR)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)

        from funerals import services as funeral_services
        self.old_funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Old Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2025-01-01", collection_start_date="2025-01-01",
        )
        self.obligation = ContributionObligation.objects.get(funeral_event=self.old_funeral, member=self.member)

    def test_requesting_a_correction_does_not_change_the_balance_yet(self):
        services.request_arrears_correction(obligation=self.obligation, amount=Decimal("50"), method="cash", reason="Member showed a handwritten receipt from last year", actor=self.arrears_collector)
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.balance, Decimal("50"))

    def test_a_plain_member_cannot_request_a_correction(self):
        plain = User.objects.create_user(username="acw_plain", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        with self.assertRaises(ValidationError):
            services.request_arrears_correction(obligation=self.obligation, amount=Decimal("50"), method="cash", reason="test", actor=plain)

    def test_the_treasurer_approving_actually_creates_a_real_payment(self):
        correction = services.request_arrears_correction(obligation=self.obligation, amount=Decimal("50"), method="cash", reason="Member showed a receipt", actor=self.arrears_collector)
        services.approve_arrears_correction(correction=correction, actor=self.treasurer)
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.balance, Decimal("0"))
        correction.refresh_from_db()
        self.assertIsNotNone(correction.resulting_payment)

    def test_the_same_person_cannot_request_and_approve_their_own_correction(self):
        correction = services.request_arrears_correction(obligation=self.obligation, amount=Decimal("50"), method="cash", reason="test", actor=self.arrears_collector)
        with self.assertRaises(ValidationError):
            services.approve_arrears_correction(correction=correction, actor=self.arrears_collector)

    def test_a_secretary_cannot_approve_an_arrears_correction(self):
        """Deliberately narrower than payment reversal approval, this is specifically the Treasurer's own call."""
        secretary = User.objects.create_user(username="acw_secretary", password="x", community=self.bodi, role=Role.SECRETARY)
        correction = services.request_arrears_correction(obligation=self.obligation, amount=Decimal("50"), method="cash", reason="test", actor=self.arrears_collector)
        with self.assertRaises(ValidationError):
            services.approve_arrears_correction(correction=correction, actor=secretary)

    def test_rejecting_a_correction_leaves_the_balance_unchanged(self):
        correction = services.request_arrears_correction(obligation=self.obligation, amount=Decimal("50"), method="cash", reason="test", actor=self.arrears_collector)
        services.reject_arrears_correction(correction=correction, actor=self.treasurer, notes="Could not verify the receipt")
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.balance, Decimal("50"))
        correction.refresh_from_db()
        self.assertEqual(correction.status, ArrearsCorrectionRequest.Status.REJECTED)

    def test_a_decided_correction_cannot_be_decided_again(self):
        correction = services.request_arrears_correction(obligation=self.obligation, amount=Decimal("50"), method="cash", reason="test", actor=self.arrears_collector)
        services.approve_arrears_correction(correction=correction, actor=self.treasurer)
        with self.assertRaises(ValidationError):
            services.approve_arrears_correction(correction=correction, actor=self.admin)

    def test_full_http_round_trip_request_and_approve(self):
        request_client = APIClient()
        login = request_client.post("/api/auth/login/", {"username": "acw_arrears_collector", "password": "a-real-password-123"})
        request_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        request_res = request_client.post(
            f"/api/obligations/{self.obligation.id}/request-arrears-correction/",
            {"amount": "50", "method": "cash", "reason": "Member showed a receipt"},
            format="json",
        )
        self.assertEqual(request_res.status_code, 201, request_res.data)

        treasurer_client = APIClient()
        treasurer_login = treasurer_client.post("/api/auth/login/", {"username": "acw_treasurer", "password": "a-real-password-123"})
        treasurer_client.credentials(HTTP_AUTHORIZATION=f"Bearer {treasurer_login.data['access']}")
        approve_res = treasurer_client.post(f"/api/arrears-corrections/{request_res.data['id']}/approve/", {}, format="json")
        self.assertEqual(approve_res.status_code, 200, approve_res.data)
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.balance, Decimal("0"))
