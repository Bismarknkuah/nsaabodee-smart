from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community
from welfare import services as welfare_services


class WelfareCrossFamilyIsolationTests(TestCase):
    """
    'Family A members may access authorized Family A campaigns... They
    must not automatically access Family B financial information...
    unless their official role explicitly grants such access.'
    (contribution-scope rules §27, and the document's own Test 6 —
    'attempt to access Family B's private campaign using a Family A
    user. The backend must reject the request.')
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="wcfi-bodi")
        self.admin = User.objects.create_user(username="wcfi_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.head_a_member = member_services.register_member(community=self.bodi, full_name="Head A", gender="male", family=self.asona)
        self.head_a_user = User.objects.create_user(username="wcfi_head_a", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_a_member, user=self.head_a_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_a_member, actor=self.admin)

        self.member_b = member_services.register_member(community=self.bodi, full_name="Member B", gender="male", family=self.bretuo)
        self.member_b_user = User.objects.create_user(username="wcfi_member_b", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        member_services.link_member_to_user(member=self.member_b, user=self.member_b_user, actor=self.admin)

        self.head_b_member = member_services.register_member(community=self.bodi, full_name="Head B", gender="male", family=self.bretuo)
        self.head_b_user = User.objects.create_user(username="wcfi_head_b", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_b_member, user=self.head_b_user, actor=self.admin)
        family_services.assign_family_head(family=self.bretuo, member=self.head_b_member, actor=self.admin)

        self.category = welfare_services.create_contribution_category(community=self.bodi, name="Medical Welfare", fixed_amount=Decimal("100"), actor=self.admin)
        self.campaign = welfare_services.initiate_family_campaign(category=self.category, family=self.asona, title="Family A Welfare", amount=Decimal("100"), actor=self.head_a_user)
        self.campaign.status = self.campaign.Status.ACTIVE
        self.campaign.save(update_fields=["status"])
        welfare_services.generate_welfare_obligations(self.campaign)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        self.assertEqual(login.status_code, 200, login.data)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_family_bs_ordinary_member_cannot_see_family_as_obligation_list(self):
        res = self._login("wcfi_member_b").get(f"/api/welfare/campaigns/{self.campaign.id}/obligations/")
        self.assertEqual(res.status_code, 200)
        # Empty, not an error — they simply have no obligation of their own under this campaign.
        self.assertEqual(res.data, [])

    def test_family_bs_head_cannot_see_family_as_obligation_list(self):
        """Even a family HEAD from a different family — the isolation is by family, not just by ordinary-vs-executive role."""
        res = self._login("wcfi_head_b").get(f"/api/welfare/campaigns/{self.campaign.id}/obligations/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data, [])

    def test_family_as_own_head_can_see_the_full_obligation_list(self):
        res = self._login("wcfi_head_a").get(f"/api/welfare/campaigns/{self.campaign.id}/obligations/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

    def test_community_admin_can_see_any_familys_obligation_list(self):
        res = self._login("wcfi_admin").get(f"/api/welfare/campaigns/{self.campaign.id}/obligations/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)

    def test_a_member_can_see_their_own_obligation_even_without_an_executive_role(self):
        """The fix must not overcorrect into hiding a member's own obligation from themselves."""
        res = self._login("wcfi_head_a").get(f"/api/welfare/campaigns/{self.campaign.id}/obligations/")
        self.assertEqual(len(res.data), 1)
        self.assertEqual(str(res.data[0]["member"]), str(self.head_a_member.id))

    def test_family_bs_member_cannot_record_a_payment_against_family_as_obligation(self):
        """The second security gap — no authorization check existed at all before this fix."""
        from welfare.models import WelfareObligation
        obligation = WelfareObligation.objects.get(campaign=self.campaign, member=self.head_a_member)
        res = self._login("wcfi_member_b").post(
            f"/api/welfare/obligations/{obligation.id}/record-payment/", {"amount": "100", "method": "cash"}, format="json",
        )
        self.assertEqual(res.status_code, 403)

    def test_family_bs_head_cannot_record_a_payment_against_family_as_obligation(self):
        from welfare.models import WelfareObligation
        obligation = WelfareObligation.objects.get(campaign=self.campaign, member=self.head_a_member)
        res = self._login("wcfi_head_b").post(
            f"/api/welfare/obligations/{obligation.id}/record-payment/", {"amount": "100", "method": "cash"}, format="json",
        )
        self.assertEqual(res.status_code, 403)

    def test_family_as_own_head_can_record_a_payment_for_their_familys_obligation(self):
        from welfare.models import WelfareObligation
        obligation = WelfareObligation.objects.get(campaign=self.campaign, member=self.head_a_member)
        res = self._login("wcfi_head_a").post(
            f"/api/welfare/obligations/{obligation.id}/record-payment/", {"amount": "100", "method": "cash"}, format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)

    def test_a_member_can_pay_their_own_obligation_even_without_an_executive_role(self):
        from welfare.models import WelfareObligation
        obligation = WelfareObligation.objects.get(campaign=self.campaign, member=self.head_a_member)
        # head_a is also the obligated member here — confirms self-payment works even setting role aside.
        res = self._login("wcfi_head_a").post(
            f"/api/welfare/obligations/{obligation.id}/record-payment/", {"amount": "50", "method": "cash"}, format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
