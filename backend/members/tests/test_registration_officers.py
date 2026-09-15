from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community


class FamilyRegistrationOfficerTests(TestCase):
    """'Each family will have their registration officer, who will register for only his family members.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="fro-bodi")
        self.admin = User.objects.create_user(username="fro_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.officer_member = member_services.register_member(community=self.bodi, full_name="The Officer", gender="male", family=self.asona)
        self.officer_user = User.objects.create_user(username="fro_officer", password="x", community=self.bodi, role=Role.FAMILY_REGISTRATION_OFFICER)
        member_services.link_member_to_user(member=self.officer_member, user=self.officer_user, actor=self.admin)

    def test_the_officer_can_register_a_member_into_their_own_family(self):
        member = member_services.register_member(community=self.bodi, full_name="New Asona Member", gender="male", family=self.asona, registered_by=self.officer_user)
        self.assertEqual(member.family_id, self.asona.id)

    def test_the_officer_cannot_register_a_member_into_a_different_family(self):
        with self.assertRaises(ValidationError):
            member_services.register_member(community=self.bodi, full_name="Should Fail", gender="male", family=self.bretuo, registered_by=self.officer_user)


class TownRegistrationOfficerTests(TestCase):
    """'Registration officer who will register the town elders.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="tro-bodi")
        self.admin = User.objects.create_user(username="tro_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.officer_user = User.objects.create_user(username="tro_officer", password="x", community=self.bodi, role=Role.TOWN_REGISTRATION_OFFICER)

    def test_the_officer_can_register_a_town_elder(self):
        member = member_services.register_member(
            community=self.bodi, full_name="A Chief", gender="male", family=self.asona,
            is_town_leader=True, registered_by=self.officer_user,
        )
        self.assertTrue(member.is_town_leader)

    def test_the_officer_cannot_register_an_ordinary_member(self):
        with self.assertRaises(ValidationError):
            member_services.register_member(
                community=self.bodi, full_name="Ordinary Person", gender="male", family=self.asona,
                is_town_leader=False, registered_by=self.officer_user,
            )

    def test_the_officer_is_not_restricted_to_one_family_for_elders(self):
        """Town elders aren't tied to one family — the officer's jurisdiction is community-wide, just elders-only."""
        bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        member = member_services.register_member(
            community=self.bodi, full_name="Another Elder", gender="male", family=bretuo,
            is_town_leader=True, registered_by=self.officer_user,
        )
        self.assertEqual(member.family_id, bretuo.id)


class CommunityRegistrationDeskTests(TestCase):
    """'Registration officer desks who will register the whole community and assign them to a family and a ledger.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="crd-bodi")
        self.admin = User.objects.create_user(username="crd_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        self.desk_user = User.objects.create_user(username="crd_desk", password="x", community=self.bodi, role=Role.COMMUNITY_REGISTRATION_DESK)

    def test_the_desk_can_register_into_any_family(self):
        m1 = member_services.register_member(community=self.bodi, full_name="Into Asona", gender="male", family=self.asona, registered_by=self.desk_user)
        m2 = member_services.register_member(community=self.bodi, full_name="Into Bretuo", gender="male", family=self.bretuo, registered_by=self.desk_user)
        self.assertEqual(m1.family_id, self.asona.id)
        self.assertEqual(m2.family_id, self.bretuo.id)

    def test_the_desk_can_assign_a_family_position_at_registration(self):
        """'Assign them to a family and a ledger' — family + family_position/family_seniority/is_town_leader are the existing ledger-determining fields."""
        member = member_services.register_member(
            community=self.bodi, full_name="Senior Member", gender="male", family=self.asona,
            family_seniority="senior", registered_by=self.desk_user,
        )
        self.assertEqual(member.family_seniority, "senior")


class OnePersonRegisteredOnceTests(TestCase):
    """'One person can be registered once' — the existing duplicate-detection rule, confirmed to apply regardless of which registration officer type is doing the registering."""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="oprc-bodi")
        self.admin = User.objects.create_user(username="oprc_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.desk_user = User.objects.create_user(username="oprc_desk", password="x", community=self.bodi, role=Role.COMMUNITY_REGISTRATION_DESK)

    def test_the_same_ghana_card_cannot_be_registered_twice_by_a_registration_desk(self):
        member_services.register_member(
            community=self.bodi, full_name="First Registration", gender="male", family=self.asona,
            ghana_card_number="GHA-000000000-0", registered_by=self.desk_user,
        )
        with self.assertRaises(ValidationError):
            member_services.register_member(
                community=self.bodi, full_name="Second Attempt", gender="male", family=self.asona,
                ghana_card_number="GHA-000000000-0", registered_by=self.desk_user,
            )
