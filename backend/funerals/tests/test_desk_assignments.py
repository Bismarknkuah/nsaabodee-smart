from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import FuneralDeskAssignment, FuneralDeskAssignmentApproval
from members import services as member_services
from tenants.models import Community


class DeskAssignmentAuthorityTests(TestCase):
    """
    'Only the community treasurer, community admin and the family
    treasurer are only allow to create or remove collector or assigned
    collector.' Chairman/Secretary/Family Head no longer directly
    open a desk themselves — they're the required approvers instead
    (see DeskAssignmentApprovalTests).
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-desk-authority",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="desk_auth_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chairman = User.objects.create_user(username="desk_auth_chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.secretary = User.objects.create_user(username="desk_auth_secretary", password="x", community=self.bodi, role=Role.SECRETARY)
        self.community_treasurer = User.objects.create_user(username="desk_auth_comm_treasurer", password="x", community=self.bodi, role=Role.TREASURER)

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.head_member = member_services.register_member(community=self.bodi, full_name="Desk Auth Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="desk_auth_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.secretary_member = member_services.register_member(community=self.bodi, full_name="Desk Auth Family Secretary", gender="female", family=self.asona)
        self.family_secretary_user = User.objects.create_user(username="desk_auth_family_secretary", password="x", community=self.bodi, role=Role.FAMILY_SECRETARY)
        member_services.link_member_to_user(member=self.secretary_member, user=self.family_secretary_user, actor=self.admin)

        self.treasurer_member = member_services.register_member(community=self.bodi, full_name="Desk Auth Family Treasurer", gender="male", family=self.asona)
        self.family_treasurer_user = User.objects.create_user(username="desk_auth_family_treasurer", password="x", community=self.bodi, role=Role.FAMILY_TREASURER)
        member_services.link_member_to_user(member=self.treasurer_member, user=self.family_treasurer_user, actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Desk Auth Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        self.recruit = User.objects.create_user(username="desk_auth_recruit", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)

    def test_family_treasurer_can_open_a_family_desk(self):
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.family_treasurer_user, desk_type="family", user=self.recruit)
        self.assertEqual(assignment.desk_type, "family")

    def test_family_head_can_no_longer_open_a_family_desk_directly(self):
        """A real narrowing — the Head is now an approver, not the initiator."""
        with self.assertRaises(ValidationError):
            funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.head_user, desk_type="family", user=self.recruit)

    def test_family_secretary_still_cannot_open_a_family_desk(self):
        with self.assertRaises(ValidationError):
            funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.family_secretary_user, desk_type="family", user=self.recruit)

    def test_community_treasurer_can_open_a_community_desk(self):
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.community_treasurer, desk_type="community", user=self.recruit)
        self.assertEqual(assignment.desk_type, "community")

    def test_community_treasurer_can_open_a_guest_desk(self):
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.community_treasurer, desk_type="guest", user=self.recruit)
        self.assertEqual(assignment.desk_type, "guest")

    def test_chairman_can_no_longer_open_a_community_desk_directly(self):
        """A real narrowing — Chairman is now an approver, not the initiator."""
        with self.assertRaises(ValidationError):
            funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.chairman, desk_type="community", user=self.recruit)

    def test_secretary_can_no_longer_open_a_community_desk_directly(self):
        with self.assertRaises(ValidationError):
            funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.secretary, desk_type="community", user=self.recruit)

    def test_community_admin_can_still_open_any_desk_type_directly(self):
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.admin, desk_type="family", user=self.recruit)
        self.assertTrue(assignment.is_active)

    def test_a_different_familys_treasurer_cannot_open_a_desk_for_this_family(self):
        bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        other_treasurer_member = member_services.register_member(community=self.bodi, full_name="Other Family Treasurer", gender="male", family=bretuo)
        other_treasurer_user = User.objects.create_user(username="desk_auth_other_treasurer", password="x", community=self.bodi, role=Role.FAMILY_TREASURER)
        member_services.link_member_to_user(member=other_treasurer_member, user=other_treasurer_user, actor=self.admin)

        with self.assertRaises(ValidationError):
            funeral_services.assign_desk_worker(funeral=self.funeral, actor=other_treasurer_user, desk_type="family", user=self.recruit)


class DeskAssignmentApprovalTests(TestCase):
    """
    'The family treasurer needs the approval of the family secretary
    and the family head... the community treasurer also needs the
    community chairman and the secretary to approve.' Two specific,
    named roles, both genuinely required — not just any two people.
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-desk-approval-new",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="desk_appr_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chairman = User.objects.create_user(username="desk_appr_chairman", password="a-real-password-123", community=self.bodi, role=Role.CHAIRMAN)
        self.secretary = User.objects.create_user(username="desk_appr_secretary", password="a-real-password-123", community=self.bodi, role=Role.SECRETARY)
        self.community_treasurer = User.objects.create_user(username="desk_appr_comm_treasurer", password="a-real-password-123", community=self.bodi, role=Role.TREASURER)
        self.other_community_admin = User.objects.create_user(username="desk_appr_other_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.head_member = member_services.register_member(community=self.bodi, full_name="Desk Appr Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="desk_appr_head", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.secretary_member = member_services.register_member(community=self.bodi, full_name="Desk Appr Family Secretary", gender="female", family=self.asona)
        self.family_secretary_user = User.objects.create_user(username="desk_appr_family_secretary", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_SECRETARY)
        member_services.link_member_to_user(member=self.secretary_member, user=self.family_secretary_user, actor=self.admin)

        self.treasurer_member = member_services.register_member(community=self.bodi, full_name="Desk Appr Family Treasurer", gender="male", family=self.asona)
        self.family_treasurer_user = User.objects.create_user(username="desk_appr_family_treasurer", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_TREASURER)
        member_services.link_member_to_user(member=self.treasurer_member, user=self.family_treasurer_user, actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Desk Appr Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        self.recruit = User.objects.create_user(username="desk_appr_recruit", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_MEMBER)

    # --- Family desk: Family Secretary + Family Head both required ---

    def test_family_desk_starts_inactive_when_treasurer_initiates(self):
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.family_treasurer_user, desk_type="family", user=self.recruit)
        self.assertFalse(assignment.is_active)

    def test_only_one_of_the_two_required_family_approvers_is_not_enough(self):
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.family_treasurer_user, desk_type="family", user=self.recruit)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.family_secretary_user)
        assignment.refresh_from_db()
        self.assertFalse(assignment.is_active)

    def test_both_family_secretary_and_family_head_approving_activates_it(self):
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.family_treasurer_user, desk_type="family", user=self.recruit)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.family_secretary_user)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.head_user)
        assignment.refresh_from_db()
        self.assertTrue(assignment.is_active)

    def test_the_same_person_approving_twice_does_not_satisfy_both_requirements(self):
        """The whole point of naming two distinct roles — one person can't stand in for both."""
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.family_treasurer_user, desk_type="family", user=self.recruit)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.family_secretary_user)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.family_secretary_user)
        assignment.refresh_from_db()
        self.assertFalse(assignment.is_active)
        self.assertEqual(FuneralDeskAssignmentApproval.objects.filter(desk_assignment=assignment).count(), 1)

    def test_a_family_treasurer_from_a_different_family_cannot_approve(self):
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.family_treasurer_user, desk_type="family", user=self.recruit)
        bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        other_head_member = member_services.register_member(community=self.bodi, full_name="Other Head", gender="male", family=bretuo)
        other_head_user = User.objects.create_user(username="desk_appr_other_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=other_head_member, user=other_head_user, actor=self.admin)
        with self.assertRaises(ValidationError):
            funeral_services.approve_desk_assignment(assignment=assignment, actor=other_head_user)

    def test_a_community_admin_opening_a_family_desk_directly_is_immediately_active(self):
        """That authority already IS the approval — no separate sign-off needed."""
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.admin, desk_type="family", user=self.recruit)
        self.assertTrue(assignment.is_active)

    # --- Community desk: Chairman + Secretary both required ---

    def test_community_desk_starts_inactive_when_treasurer_initiates(self):
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.community_treasurer, desk_type="community", user=self.recruit)
        self.assertFalse(assignment.is_active)

    def test_only_chairman_approving_is_not_enough(self):
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.community_treasurer, desk_type="community", user=self.recruit)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.chairman)
        assignment.refresh_from_db()
        self.assertFalse(assignment.is_active)

    def test_both_chairman_and_secretary_approving_activates_a_community_desk(self):
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.community_treasurer, desk_type="community", user=self.recruit)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.chairman)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.secretary)
        assignment.refresh_from_db()
        self.assertTrue(assignment.is_active)

    def test_both_chairman_and_secretary_approving_activates_a_guest_desk(self):
        """'For either gift collection or contribution collector' — Guest desk (gifts) works the same way as Community desk (contributions)."""
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.community_treasurer, desk_type="guest", user=self.recruit)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.chairman)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.secretary)
        assignment.refresh_from_db()
        self.assertTrue(assignment.is_active)

    def test_family_head_cannot_approve_a_community_desk(self):
        """Family-level approvers don't cross over into community-level approvals."""
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.community_treasurer, desk_type="community", user=self.recruit)
        with self.assertRaises(ValidationError):
            funeral_services.approve_desk_assignment(assignment=assignment, actor=self.head_user)

    def test_a_pending_assignment_grants_no_real_desk_access_yet(self):
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.community_treasurer, desk_type="community", user=self.recruit)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.chairman)  # only one of two
        from funerals.permissions import is_desk_worker_for
        self.assertFalse(is_desk_worker_for(self.recruit, self.funeral, "contributions"))

    def test_full_activation_genuinely_grants_desk_access(self):
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.community_treasurer, desk_type="community", user=self.recruit)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.chairman)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.secretary)
        from funerals.permissions import is_desk_worker_for
        self.assertTrue(is_desk_worker_for(self.recruit, self.funeral, "contributions"))

    def test_family_desk_grants_both_contribution_and_gift_capability(self):
        """'The family collector is also allow to receive family contribution or gifts.'"""
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.family_treasurer_user, desk_type="family", user=self.recruit)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.family_secretary_user)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.head_user)
        from funerals.permissions import is_desk_worker_for
        self.assertTrue(is_desk_worker_for(self.recruit, self.funeral, "contributions"))
        self.assertTrue(is_desk_worker_for(self.recruit, self.funeral, "gifts"))

    # --- Pending queue, scoped per eligible approver ---

    def test_family_secretary_sees_the_pending_family_desk_in_their_own_queue(self):
        funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.family_treasurer_user, desk_type="family", user=self.recruit)
        pending = funeral_services.list_pending_desk_assignments_for(self.family_secretary_user)
        self.assertEqual(pending.count(), 1)

    def test_chairman_sees_the_pending_community_desk_but_not_a_pending_family_desk(self):
        second_recruit = User.objects.create_user(username="desk_appr_recruit_2", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.community_treasurer, desk_type="community", user=self.recruit)
        funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.family_treasurer_user, desk_type="family", user=second_recruit)
        pending = funeral_services.list_pending_desk_assignments_for(self.chairman)
        self.assertEqual(pending.count(), 1)
        self.assertEqual(pending.first().desk_type, "community")

    def test_a_family_head_from_a_different_family_sees_nothing_in_their_queue(self):
        funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.family_treasurer_user, desk_type="family", user=self.recruit)
        bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        other_head_member = member_services.register_member(community=self.bodi, full_name="Other Head", gender="male", family=bretuo)
        other_head_user = User.objects.create_user(username="desk_appr_other_head_2", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=other_head_member, user=other_head_user, actor=self.admin)
        pending = funeral_services.list_pending_desk_assignments_for(other_head_user)
        self.assertEqual(pending.count(), 0)

    # --- HTTP round-trip ---

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_http_round_trip_community_desk_dual_approval(self):
        treasurer_client = self._login("desk_appr_comm_treasurer")
        assign_res = treasurer_client.post(f"/api/funerals/{self.funeral.id}/desk-assignments/", {"desk_type": "community", "user_id": str(self.recruit.id)})
        self.assertEqual(assign_res.status_code, 201)
        self.assertFalse(assign_res.data["is_active"])
        assignment_id = assign_res.data["id"]

        chairman_client = self._login("desk_appr_chairman")
        pending_res = chairman_client.get("/api/desk-assignments/pending/")
        self.assertEqual(pending_res.status_code, 200)
        self.assertEqual(len(pending_res.data), 1)

        first_approve = chairman_client.post(f"/api/desk-assignments/{assignment_id}/approve/")
        self.assertEqual(first_approve.status_code, 200)
        self.assertFalse(first_approve.data["is_active"])

        secretary_client = self._login("desk_appr_secretary")
        second_approve = secretary_client.post(f"/api/desk-assignments/{assignment_id}/approve/")
        self.assertEqual(second_approve.status_code, 200)
        self.assertTrue(second_approve.data["is_active"])
