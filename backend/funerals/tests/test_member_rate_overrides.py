from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import ContributionObligation, FuneralEvent
from members import services as member_services
from tenants.models import Community


class MemberRateOverrideServiceTests(TestCase):
    """
    'The family head and secretary of the deceased family can set an
    amount for each member [of their own family] have to pay' — a
    per-person override on top of the community's tiered defaults.
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
            default_family_head_amount=Decimal("200"), default_family_junior_amount=Decimal("50"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.secretary = User.objects.create_user(username="secretary", password="x", community=self.bodi, role=Role.SECRETARY)
        self.chairman = User.objects.create_user(username="chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.head_member = member_services.register_member(community=self.bodi, full_name="The Head", gender="male", family=self.asona)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)
        self.ordinary_member = member_services.register_member(community=self.bodi, full_name="Ordinary", gender="male", family=self.asona)

        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.outsider_member = member_services.register_member(community=self.bodi, full_name="Outsider", gender="male", family=self.bretuo)

        self.funeral = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def test_override_replaces_the_tiered_default_once_activated(self):
        funeral_services.set_member_rate_overrides(
            funeral=self.funeral, overrides={str(self.ordinary_member.id): Decimal("999")}, actor=self.head_member.linked_user
        )
        funeral_services.approve_funeral_opening(funeral=self.funeral, approver=self.secretary)
        funeral_services.approve_funeral_opening(funeral=self.funeral, approver=self.chairman)

        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.ordinary_member)
        self.assertEqual(obligation.expected_amount, Decimal("999"))
        self.assertEqual(obligation.rate_type, "own_family")

    def test_a_member_with_no_override_still_gets_the_normal_tiered_rate(self):
        funeral_services.set_member_rate_overrides(funeral=self.funeral, overrides={str(self.ordinary_member.id): Decimal("999")})
        funeral_services.approve_funeral_opening(funeral=self.funeral, approver=self.secretary)
        funeral_services.approve_funeral_opening(funeral=self.funeral, approver=self.chairman)

        head_obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.head_member)
        self.assertEqual(head_obligation.expected_amount, Decimal("200"))  # untouched, normal head rate

    def test_cannot_set_an_override_for_a_member_outside_the_deceased_family(self):
        with self.assertRaises(ValidationError):
            funeral_services.set_member_rate_overrides(funeral=self.funeral, overrides={str(self.outsider_member.id): Decimal("500")})

    def test_cannot_set_overrides_once_the_funeral_is_already_active(self):
        funeral_services.approve_funeral_opening(funeral=self.funeral, approver=self.secretary)
        funeral_services.approve_funeral_opening(funeral=self.funeral, approver=self.chairman)
        with self.assertRaises(ValidationError):
            funeral_services.set_member_rate_overrides(funeral=self.funeral, overrides={str(self.ordinary_member.id): Decimal("999")})

    def test_negative_amount_rejected(self):
        with self.assertRaises(ValidationError):
            funeral_services.set_member_rate_overrides(funeral=self.funeral, overrides={str(self.ordinary_member.id): Decimal("-10")})

    def test_setting_an_override_twice_for_the_same_member_updates_it_not_duplicates(self):
        funeral_services.set_member_rate_overrides(funeral=self.funeral, overrides={str(self.ordinary_member.id): Decimal("100")})
        funeral_services.set_member_rate_overrides(funeral=self.funeral, overrides={str(self.ordinary_member.id): Decimal("150")})
        overrides = funeral_services.list_member_rate_overrides(self.funeral)
        self.assertEqual(len(overrides), 1)
        self.assertEqual(overrides[0].amount, Decimal("150"))


class MemberRateOverrideHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

        self.head_member = member_services.register_member(community=self.bodi, full_name="The Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="the_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.ordinary_member = member_services.register_member(community=self.bodi, full_name="Ordinary", gender="male", family=self.asona)

        self.other_family_head_user = User.objects.create_user(username="other_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        other_head_member = member_services.register_member(community=self.bodi, full_name="Other Head", gender="male", family=self.bretuo)
        member_services.link_member_to_user(member=other_head_member, user=self.other_family_head_user, actor=self.admin)
        family_services.assign_family_head(family=self.bretuo, member=other_head_member, actor=self.admin)

        self.funeral = funeral_services.request_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_the_deceased_familys_own_head_can_set_overrides(self):
        client = self._login("the_head")
        res = client.post(f"/api/funerals/{self.funeral.id}/member-rate-overrides/", {
            "overrides": {str(self.ordinary_member.id): "777"}
        }, format="json")
        self.assertEqual(res.status_code, 201)

    def test_a_different_familys_head_cannot_set_overrides_on_this_funeral(self):
        client = self._login("other_head")
        res = client.post(f"/api/funerals/{self.funeral.id}/member-rate-overrides/", {
            "overrides": {str(self.ordinary_member.id): "777"}
        }, format="json")
        self.assertEqual(res.status_code, 403)
