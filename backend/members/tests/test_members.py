from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from members import services
from members.models import Member
from tenants.models import Community


class MemberRegistrationTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(
            username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN
        )
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

    def test_register_member_auto_generates_membership_number(self):
        member = services.register_member(
            community=self.bodi, full_name="Kojo Mensah", gender="male", family=self.asona, registered_by=self.admin
        )
        self.assertTrue(member.membership_number.startswith("BODI-"))

    def test_two_members_get_distinct_membership_numbers(self):
        m1 = services.register_member(community=self.bodi, full_name="A", gender="male", family=self.asona)
        m2 = services.register_member(community=self.bodi, full_name="B", gender="female", family=self.asona)
        self.assertNotEqual(m1.membership_number, m2.membership_number)

    def test_duplicate_ghana_card_number_rejected(self):
        services.register_member(
            community=self.bodi, full_name="Kojo Mensah", gender="male", family=self.asona,
            ghana_card_number="GHA-000111222-1",
        )
        with self.assertRaises(ValidationError):
            services.register_member(
                community=self.bodi, full_name="Someone Else", gender="male", family=self.asona,
                ghana_card_number="GHA-000111222-1",
            )

    def test_same_ghana_card_number_allowed_across_different_communities(self):
        other = Community.objects.create(name="Other Community", slug="other")
        services.register_member(
            community=self.bodi, full_name="Kojo", gender="male", ghana_card_number="GHA-000111222-1"
        )
        # Should not raise:
        services.register_member(
            community=other, full_name="Kojo", gender="male", ghana_card_number="GHA-000111222-1"
        )

    def test_family_must_belong_to_same_community(self):
        other = Community.objects.create(name="Other Community", slug="other")
        with self.assertRaises(ValidationError):
            services.register_member(community=other, full_name="Kojo", gender="male", family=self.asona)

    def test_find_possible_duplicates_by_name_or_phone(self):
        services.register_member(community=self.bodi, full_name="Ama Serwaa", gender="female", phone="0244000111")
        duplicates = services.find_possible_duplicates(community=self.bodi, full_name="Ama Serwaa", phone="0200000000")
        self.assertEqual(len(duplicates), 1)
        duplicates_by_phone = services.find_possible_duplicates(community=self.bodi, full_name="Totally Different", phone="0244000111")
        self.assertEqual(len(duplicates_by_phone), 1)

    def test_qr_and_digital_card_generation(self):
        member = services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)
        card = services.digital_membership_card(member)
        self.assertEqual(card["membership_number"], member.membership_number)
        self.assertEqual(card["family_name"], "Asona")
        self.assertTrue(len(card["qr_code_base64"]) > 100)


class DefaulterEscalationTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)

        self.member = services.register_member(
            community=self.bodi, full_name="Yaw Owusu", gender="male", family=self.bretuo
        )

    def _open_and_close_unpaid_funeral(self, name):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name=name, deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        funeral_services.close_funeral_event(funeral=funeral, actor=self.admin)
        return funeral

    def test_member_stays_in_good_standing_before_any_closed_funeral(self):
        self.member.refresh_from_db()
        self.assertEqual(self.member.defaulter_tier, Member.DefaulterTier.NONE)

    def test_one_missed_contribution_triggers_warning(self):
        self._open_and_close_unpaid_funeral("Funeral A")
        self.member.refresh_from_db()
        self.assertEqual(self.member.missed_contributions_count, 1)
        self.assertEqual(self.member.defaulter_tier, Member.DefaulterTier.WARNING)

    def test_three_missed_contributions_trigger_flag_and_notifications(self):
        for i in range(3):
            self._open_and_close_unpaid_funeral(f"Funeral {i}")
        self.member.refresh_from_db()
        self.assertEqual(self.member.missed_contributions_count, 3)
        self.assertEqual(self.member.defaulter_tier, Member.DefaulterTier.FLAGGED)

        from notifications.models import Notification
        self.assertTrue(Notification.objects.filter(related_member=self.member, recipient_role=Role.TREASURER).exists())

    def test_paying_in_full_before_close_prevents_a_miss(self):
        funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Funeral Paid", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        from funerals.models import ContributionObligation
        obligation = ContributionObligation.objects.get(funeral_event=funeral, member=self.member)
        funeral_services.record_payment(obligation=obligation, amount=Decimal("5"), method="cash")

        funeral_services.close_funeral_event(funeral=funeral, actor=self.admin)
        self.member.refresh_from_db()
        self.assertEqual(self.member.missed_contributions_count, 0)
        self.assertEqual(self.member.defaulter_tier, Member.DefaulterTier.NONE)

    def test_defaulter_thresholds_are_configurable(self):
        from contribution_rules import services as rule_services
        rule_services.update_defaulter_thresholds(community=self.bodi, warning=2, high_warning=4, flag=6, actor=self.admin)

        self._open_and_close_unpaid_funeral("Funeral A")
        self.member.refresh_from_db()
        self.assertEqual(self.member.defaulter_tier, Member.DefaulterTier.NONE)  # 1 miss, warning now needs 2

        self._open_and_close_unpaid_funeral("Funeral B")
        self.member.refresh_from_db()
        self.assertEqual(self.member.defaulter_tier, Member.DefaulterTier.WARNING)  # 2 misses


class MemberUserLinkingTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)
        self.member_user = User.objects.create_user(
            username="kojo_login", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER
        )

    def test_link_member_to_user(self):
        updated = services.link_member_to_user(member=self.member, user=self.member_user, actor=self.admin)
        self.assertEqual(updated.linked_user_id, self.member_user.id)

    def test_cannot_link_user_from_a_different_community(self):
        other = Community.objects.create(name="Other", slug="other")
        outsider_user = User.objects.create_user(username="outsider", password="x", community=other, role=Role.COMMUNITY_MEMBER)
        with self.assertRaises(ValidationError):
            services.link_member_to_user(member=self.member, user=outsider_user, actor=self.admin)

    def test_cannot_link_the_same_user_to_two_members(self):
        services.link_member_to_user(member=self.member, user=self.member_user, actor=self.admin)
        other_member = services.register_member(community=self.bodi, full_name="Ama", gender="female", family=self.asona)
        with self.assertRaises(ValidationError):
            services.link_member_to_user(member=other_member, user=self.member_user, actor=self.admin)

    def test_unlink_member_from_user(self):
        services.link_member_to_user(member=self.member, user=self.member_user, actor=self.admin)
        services.unlink_member_from_user(member=self.member, actor=self.admin)
        self.member.refresh_from_db()
        self.assertIsNone(self.member.linked_user_id)
