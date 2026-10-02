from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community


class FamilyTreasurerCanRecommendRateTests(TestCase):
    """
    'The family finance officer should also be in charge of anything
    related to money.' A family's own contribution rate is the single
    most consequential money decision a family makes — previously only
    a Family Head (or Community Admin+) could recommend one at all,
    leaving the Family Treasurer, the role explicitly meant to handle
    money, unable to do the one thing most squarely their job.
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="ftr-bodi")
        self.admin = User.objects.create_user(username="ftr_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.treasurer_member = member_services.register_member(community=self.bodi, full_name="Asona Treasurer", gender="male", family=self.asona)
        self.treasurer = User.objects.create_user(username="ftr_treasurer", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_TREASURER)
        member_services.link_member_to_user(member=self.treasurer_member, user=self.treasurer, actor=self.admin)

        self.plain_member_user = User.objects.create_user(username="ftr_plain_member", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_family_treasurer_can_recommend_their_own_familys_rate(self):
        client = self._login("ftr_treasurer")
        res = client.post(f"/api/families/{self.asona.id}/recommend-rate/", {"amount": "60.00"})
        self.assertEqual(res.status_code, 200, res.data)
        self.asona.refresh_from_db()
        self.assertEqual(self.asona.recommended_family_rate, Decimal("60.00"))

    def test_family_head_can_still_recommend_a_rate_unaffected_by_this_change(self):
        head_member = member_services.register_member(community=self.bodi, full_name="Asona Head", gender="male", family=self.asona)
        head = User.objects.create_user(username="ftr_head", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=head_member, user=head, actor=self.admin)
        client = self._login("ftr_head")
        res = client.post(f"/api/families/{self.asona.id}/recommend-rate/", {"amount": "55.00"})
        self.assertEqual(res.status_code, 200, res.data)

    def test_an_ordinary_community_member_still_cannot_recommend_a_rate(self):
        """This change is additive, not a general loosening — an ordinary member still can't."""
        client = self._login("ftr_plain_member")
        res = client.post(f"/api/families/{self.asona.id}/recommend-rate/", {"amount": "60.00"})
        self.assertEqual(res.status_code, 403)
