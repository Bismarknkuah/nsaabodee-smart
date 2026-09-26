from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from members.models import CollectorNomination, Member
from tenants.models import Community


class GeneralCollectorNominationTests(TestCase):
    """'1. The general collector who collects the community ledger, so the community chairman and community admin can create an account.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="gcn-bodi")
        self.admin = User.objects.create_user(username="gcn_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chairman = User.objects.create_user(username="gcn_chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.secretary = User.objects.create_user(username="gcn_secretary", password="x", community=self.bodi, role=Role.SECRETARY)
        self.treasurer = User.objects.create_user(username="gcn_treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        self.collector_user = User.objects.create_user(username="gcn_collector", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.candidate = Member.objects.create(community=self.bodi, family=self.asona, full_name="Future Collector", gender="male", linked_user=self.collector_user)

    def test_chairman_can_nominate_a_general_collector(self):
        nomination = member_services.nominate_collector(member=self.candidate, collector_type="general", actor=self.chairman)
        self.assertEqual(nomination.status, "pending")

    def test_community_admin_can_also_nominate(self):
        nomination = member_services.nominate_collector(member=self.candidate, collector_type="general", actor=self.admin)
        self.assertEqual(nomination.status, "pending")

    def test_a_treasurer_cannot_nominate_a_general_collector(self):
        with self.assertRaises(ValidationError):
            member_services.nominate_collector(member=self.candidate, collector_type="general", actor=self.treasurer)

    def test_the_member_is_not_yet_a_collector_after_nomination_alone(self):
        member_services.nominate_collector(member=self.candidate, collector_type="general", actor=self.chairman)
        self.collector_user.refresh_from_db()
        self.assertNotEqual(self.collector_user.role, "collector")

    def test_treasurer_plus_secretary_approval_activates_the_collector(self):
        nomination = member_services.nominate_collector(member=self.candidate, collector_type="general", actor=self.chairman)
        member_services.decide_collector_nomination(nomination=nomination, actor=self.treasurer, decision="approve")
        nomination.refresh_from_db()
        self.assertEqual(nomination.status, "pending")  # only one of two required groups so far
        member_services.decide_collector_nomination(nomination=nomination, actor=self.secretary, decision="approve")
        nomination.refresh_from_db()
        self.assertEqual(nomination.status, "approved")
        self.collector_user.refresh_from_db()
        self.assertEqual(self.collector_user.role, "collector")

    def test_treasurer_plus_chairman_approval_also_works_since_the_second_slot_is_either_or(self):
        nomination = member_services.nominate_collector(member=self.candidate, collector_type="general", actor=self.admin)
        member_services.decide_collector_nomination(nomination=nomination, actor=self.treasurer, decision="approve")
        member_services.decide_collector_nomination(nomination=nomination, actor=self.chairman, decision="approve")
        nomination.refresh_from_db()
        self.assertEqual(nomination.status, "approved")

    def test_secretary_and_chairman_alone_never_approves_without_the_treasurer(self):
        """The treasurer's own group is required — secretary+chairman together still isn't enough."""
        nomination = member_services.nominate_collector(member=self.candidate, collector_type="general", actor=self.admin)
        member_services.decide_collector_nomination(nomination=nomination, actor=self.secretary, decision="approve")
        member_services.decide_collector_nomination(nomination=nomination, actor=self.chairman, decision="approve")
        nomination.refresh_from_db()
        self.assertEqual(nomination.status, "pending")
        self.collector_user.refresh_from_db()
        self.assertNotEqual(self.collector_user.role, "collector")

    def test_a_single_rejection_ends_the_nomination_immediately(self):
        nomination = member_services.nominate_collector(member=self.candidate, collector_type="general", actor=self.chairman)
        member_services.decide_collector_nomination(nomination=nomination, actor=self.treasurer, decision="reject")
        nomination.refresh_from_db()
        self.assertEqual(nomination.status, "rejected")
        # Even a subsequent approve attempt is refused — the decision is final.
        with self.assertRaises(ValidationError):
            member_services.decide_collector_nomination(nomination=nomination, actor=self.secretary, decision="approve")

    def test_the_same_approver_cannot_vote_twice(self):
        nomination = member_services.nominate_collector(member=self.candidate, collector_type="general", actor=self.chairman)
        member_services.decide_collector_nomination(nomination=nomination, actor=self.treasurer, decision="approve")
        with self.assertRaises(ValidationError):
            member_services.decide_collector_nomination(nomination=nomination, actor=self.treasurer, decision="approve")

    def test_a_second_pending_nomination_for_the_same_member_is_rejected(self):
        member_services.nominate_collector(member=self.candidate, collector_type="general", actor=self.chairman)
        with self.assertRaises(ValidationError):
            member_services.nominate_collector(member=self.candidate, collector_type="general", actor=self.admin)


class FamilyAndDonationCollectorTests(TestCase):
    """'2. The family collector... the abusuapanin should have access to create the [account] to collect... 3. donation collector, the abusuapanin have to create the account.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="fdc-bodi")
        self.admin = User.objects.create_user(username="fdc_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)

        self.head_user = User.objects.create_user(username="fdc_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        self.head_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="The Head", gender="male", linked_user=self.head_user)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.treasurer_user = User.objects.create_user(username="fdc_treasurer", password="x", community=self.bodi, role=Role.FAMILY_TREASURER)
        self.treasurer_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Family Treasurer", gender="male", linked_user=self.treasurer_user)
        self.secretary_user = User.objects.create_user(username="fdc_secretary", password="x", community=self.bodi, role=Role.FAMILY_SECRETARY)
        self.secretary_member = Member.objects.create(community=self.bodi, family=self.asona, full_name="Family Secretary", gender="male", linked_user=self.secretary_user)

        self.candidate_user = User.objects.create_user(username="fdc_candidate", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        self.candidate = Member.objects.create(community=self.bodi, family=self.asona, full_name="Future Family Collector", gender="male", linked_user=self.candidate_user)

        self.outside_family_treasurer_user = User.objects.create_user(username="fdc_outside_treasurer", password="x", community=self.bodi, role=Role.FAMILY_TREASURER)
        Member.objects.create(community=self.bodi, family=self.bretuo, full_name="Other Family Treasurer", gender="male", linked_user=self.outside_family_treasurer_user)

    def test_family_head_can_nominate_a_family_collector_from_their_own_family(self):
        nomination = member_services.nominate_collector(member=self.candidate, collector_type="family", actor=self.head_user)
        self.assertEqual(nomination.scoped_family_id, self.asona.id)

    def test_family_head_cannot_nominate_someone_from_a_different_family(self):
        outsider = Member.objects.create(community=self.bodi, family=self.bretuo, full_name="Outsider", gender="male")
        with self.assertRaises(ValidationError):
            member_services.nominate_collector(member=outsider, collector_type="family", actor=self.head_user)

    def test_family_treasurer_and_secretary_together_approve_a_family_collector(self):
        nomination = member_services.nominate_collector(member=self.candidate, collector_type="family", actor=self.head_user)
        member_services.decide_collector_nomination(nomination=nomination, actor=self.treasurer_user, decision="approve")
        nomination.refresh_from_db()
        self.assertEqual(nomination.status, "pending")
        member_services.decide_collector_nomination(nomination=nomination, actor=self.secretary_user, decision="approve")
        nomination.refresh_from_db()
        self.assertEqual(nomination.status, "approved")
        self.candidate_user.refresh_from_db()
        self.assertEqual(self.candidate_user.role, "collector")

    def test_a_different_familys_treasurer_cannot_approve(self):
        """The core cross-family boundary — must never leak."""
        nomination = member_services.nominate_collector(member=self.candidate, collector_type="family", actor=self.head_user)
        with self.assertRaises(ValidationError):
            member_services.decide_collector_nomination(nomination=nomination, actor=self.outside_family_treasurer_user, decision="approve")

    def test_donation_collector_follows_the_same_family_officer_approval_rule(self):
        nomination = member_services.nominate_collector(member=self.candidate, collector_type="donation", actor=self.head_user)
        member_services.decide_collector_nomination(nomination=nomination, actor=self.treasurer_user, decision="approve")
        member_services.decide_collector_nomination(nomination=nomination, actor=self.secretary_user, decision="approve")
        nomination.refresh_from_db()
        self.assertEqual(nomination.status, "approved")

    def test_a_treasurer_cannot_nominate_a_family_collector_only_the_head_can(self):
        with self.assertRaises(ValidationError):
            member_services.nominate_collector(member=self.candidate, collector_type="family", actor=self.treasurer_user)


class TownElderCollectorTests(TestCase):
    """'4. The town elder ledger — the chief has to assign someone to collect the town elders ledger contribution... the town elders need other two executives to confirm it.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="tec-bodi")
        self.admin = User.objects.create_user(username="tec_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chief = User.objects.create_user(username="tec_chief", password="x", community=self.bodi, role=Role.TRADITIONAL_LEADER)
        self.chairman = User.objects.create_user(username="tec_chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.secretary = User.objects.create_user(username="tec_secretary", password="x", community=self.bodi, role=Role.SECRETARY)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.candidate_user = User.objects.create_user(username="tec_candidate", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        self.candidate = Member.objects.create(community=self.bodi, family=self.asona, full_name="Future Elder Collector", gender="male", linked_user=self.candidate_user)

    def test_the_chief_can_nominate_a_town_elder_collector(self):
        nomination = member_services.nominate_collector(member=self.candidate, collector_type="town_elder", actor=self.chief)
        self.assertEqual(nomination.status, "pending")

    def test_a_community_admin_cannot_nominate_a_town_elder_collector(self):
        with self.assertRaises(ValidationError):
            member_services.nominate_collector(member=self.candidate, collector_type="town_elder", actor=self.admin)

    def test_two_other_executives_approving_activates_the_collector(self):
        nomination = member_services.nominate_collector(member=self.candidate, collector_type="town_elder", actor=self.chief)
        member_services.decide_collector_nomination(nomination=nomination, actor=self.chairman, decision="approve")
        nomination.refresh_from_db()
        self.assertEqual(nomination.status, "pending")
        member_services.decide_collector_nomination(nomination=nomination, actor=self.secretary, decision="approve")
        nomination.refresh_from_db()
        self.assertEqual(nomination.status, "approved")


class CollectorHttpEndpointTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="ceh-bodi")
        self.admin = User.objects.create_user(username="ceh_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chairman = User.objects.create_user(username="ceh_chairman", password="a-real-password-123", community=self.bodi, role=Role.CHAIRMAN)
        self.treasurer = User.objects.create_user(username="ceh_treasurer", password="a-real-password-123", community=self.bodi, role=Role.TREASURER)
        self.secretary = User.objects.create_user(username="ceh_secretary", password="a-real-password-123", community=self.bodi, role=Role.SECRETARY)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.candidate_user = User.objects.create_user(username="ceh_candidate", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        self.candidate = Member.objects.create(community=self.bodi, family=self.asona, full_name="HTTP Candidate", gender="male", linked_user=self.candidate_user)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_http_nomination_and_approval_round_trip(self):
        client = self._login("ceh_chairman")
        res = client.post("/api/members/collector-nominations/", {"member_id": str(self.candidate.id), "collector_type": "general"}, format="json")
        self.assertEqual(res.status_code, 201)
        nomination_id = res.data["id"]

        client2 = self._login("ceh_treasurer")
        res2 = client2.post(f"/api/members/collector-nominations/{nomination_id}/decide/", {"decision": "approve"}, format="json")
        self.assertEqual(res2.status_code, 200)

        client3 = self._login("ceh_secretary")
        res3 = client3.post(f"/api/members/collector-nominations/{nomination_id}/decide/", {"decision": "approve"}, format="json")
        self.assertEqual(res3.status_code, 200)
        self.assertEqual(res3.data["status"], "approved")

        self.candidate_user.refresh_from_db()
        self.assertEqual(self.candidate_user.role, "collector")

    def test_full_http_list_nominations(self):
        member_services.nominate_collector(member=self.candidate, collector_type="general", actor=self.chairman)
        client = self._login("ceh_admin")
        res = client.get("/api/members/collector-nominations/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
