from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import ContributionObligation, FuneralDeskAssignment, FuneralEvent
from members import services as member_services
from tenants.models import Community


class DeskAssignmentServiceTests(TestCase):
    """
    'The community chairman or secretary can open two or more community
    ledger payment desks... a separate desk for the community elders...
    one or more guest payment desks... the abusuapanin/head and
    secretary of the deceased family can also create family desks.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chairman = User.objects.create_user(username="chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.secretary = User.objects.create_user(username="secretary", password="x", community=self.bodi, role=Role.SECRETARY)

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.head_member = member_services.register_member(community=self.bodi, full_name="The Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="the_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.bretuo = family_services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        other_head_member = member_services.register_member(community=self.bodi, full_name="Other Head", gender="male", family=self.bretuo)
        self.other_head_user = User.objects.create_user(username="other_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=other_head_member, user=self.other_head_user, actor=self.admin)
        family_services.assign_family_head(family=self.bretuo, member=other_head_member, actor=self.admin)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        self.ordinary_user = User.objects.create_user(username="ordinary", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)

    def test_chairman_can_open_a_community_desk(self):
        assignment = funeral_services.assign_desk_worker(
            funeral=self.funeral, actor=self.chairman, desk_type=FuneralDeskAssignment.DeskType.COMMUNITY, user=self.ordinary_user,
        )
        self.assertEqual(assignment.desk_type, "community")

    def test_secretary_can_open_two_community_desks_with_different_people(self):
        second_user = User.objects.create_user(username="second_desk_worker", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.secretary, desk_type="community", user=self.ordinary_user)
        funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.secretary, desk_type="community", user=second_user)
        community_desks = [a for a in funeral_services.list_desk_assignments(self.funeral) if a.desk_type == "community"]
        self.assertEqual(len(community_desks), 2)

    def test_chairman_can_open_an_elders_desk(self):
        assignment = funeral_services.assign_desk_worker(
            funeral=self.funeral, actor=self.chairman, desk_type=FuneralDeskAssignment.DeskType.ELDERS, user=self.ordinary_user,
        )
        self.assertEqual(assignment.desk_type, "elders")

    def test_secretary_can_open_a_guest_desk(self):
        assignment = funeral_services.assign_desk_worker(
            funeral=self.funeral, actor=self.secretary, desk_type=FuneralDeskAssignment.DeskType.GUEST, user=self.ordinary_user,
        )
        self.assertEqual(assignment.desk_type, "guest")

    def test_family_head_can_open_a_family_desk_for_his_own_family(self):
        assignment = funeral_services.assign_desk_worker(
            funeral=self.funeral, actor=self.head_user, desk_type=FuneralDeskAssignment.DeskType.FAMILY, user=self.ordinary_user,
        )
        self.assertEqual(assignment.desk_type, "family")

    def test_family_head_cannot_open_a_community_desk(self):
        """The Community/Elders/Guest desk purposes serve the whole community — a family head has no authority to open them, even for his own funeral."""
        with self.assertRaises(ValidationError):
            funeral_services.assign_desk_worker(
                funeral=self.funeral, actor=self.head_user, desk_type=FuneralDeskAssignment.DeskType.COMMUNITY, user=self.ordinary_user,
            )

    def test_family_head_cannot_open_a_family_desk_for_a_different_family(self):
        with self.assertRaises(ValidationError):
            funeral_services.assign_desk_worker(
                funeral=self.funeral, actor=self.other_head_user, desk_type=FuneralDeskAssignment.DeskType.FAMILY, user=self.ordinary_user,
            )

    def test_ordinary_community_member_cannot_open_any_desk(self):
        another_user = User.objects.create_user(username="another", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)
        with self.assertRaises(ValidationError):
            funeral_services.assign_desk_worker(
                funeral=self.funeral, actor=self.ordinary_user, desk_type=FuneralDeskAssignment.DeskType.GUEST, user=another_user,
            )

    def test_a_community_desk_worker_can_record_a_contribution_payment(self):
        funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.chairman, desk_type="community", user=self.ordinary_user)
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.head_member)
        client = self._login("ordinary")
        res = client.post(f"/api/funerals/{self.funeral.id}/obligations/{obligation.id}/record-payment/", {"amount": "50", "method": "cash"})
        self.assertEqual(res.status_code, 201)

    def test_a_guest_desk_worker_can_record_a_gift_but_not_a_contribution(self):
        funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.secretary, desk_type="guest", user=self.ordinary_user)
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.head_member)
        client = self._login("ordinary")

        gift_res = client.post(f"/api/funerals/{self.funeral.id}/gifts/", {"donor_name": "A Guest", "amount_cash": "20"})
        self.assertEqual(gift_res.status_code, 201)

        payment_res = client.post(f"/api/funerals/{self.funeral.id}/obligations/{obligation.id}/record-payment/", {"amount": "50", "method": "cash"})
        self.assertEqual(payment_res.status_code, 403)

    def test_an_elders_desk_worker_can_record_both_a_contribution_and_a_gift(self):
        """The Elders desk grants both — an elder might pay their flat mandatory rate AND give an extra voluntary gift at the same table."""
        funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.chairman, desk_type="elders", user=self.ordinary_user)
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.head_member)
        client = self._login("ordinary")

        payment_res = client.post(f"/api/funerals/{self.funeral.id}/obligations/{obligation.id}/record-payment/", {"amount": "50", "method": "cash"})
        gift_res = client.post(f"/api/funerals/{self.funeral.id}/gifts/", {
            "donor_name": "An Elder", "amount_cash": "50", "donor_category": "town_leader",
        })
        self.assertEqual(payment_res.status_code, 201)
        self.assertEqual(gift_res.status_code, 201)

    def test_a_family_desk_worker_can_record_both_contributions_and_gifts(self):
        """
        'Can assign someone to receive family contribution and donating
        of gifts to deceased family members' — a Family desk now covers
        both, the same way an Elders desk always has. This test used to
        assert the opposite (gifts rejected); that was the actual gap
        this change fixed, not a regression to preserve.
        """
        funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.head_user, desk_type="family", user=self.ordinary_user)
        assignment = FuneralDeskAssignment.objects.get(funeral_event=self.funeral, user=self.ordinary_user)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.admin)
        obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.head_member)
        client = self._login("ordinary")

        payment_res = client.post(f"/api/funerals/{self.funeral.id}/obligations/{obligation.id}/record-payment/", {"amount": "50", "method": "cash"})
        gift_res = client.post(f"/api/funerals/{self.funeral.id}/gifts/", {"donor_name": "A Guest", "amount_cash": "20"})
        self.assertEqual(payment_res.status_code, 201)
        self.assertEqual(gift_res.status_code, 201)

    def test_removing_a_desk_assignment_revokes_access(self):
        funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.chairman, desk_type="community", user=self.ordinary_user)
        funeral_services.remove_desk_worker(funeral=self.funeral, user=self.ordinary_user, actor=self.chairman)
        self.assertFalse(FuneralDeskAssignment.objects.filter(funeral_event=self.funeral, user=self.ordinary_user).exists())

    def test_family_head_can_remove_his_own_family_desk_assignment(self):
        funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.head_user, desk_type="family", user=self.ordinary_user)
        funeral_services.remove_desk_worker(funeral=self.funeral, user=self.ordinary_user, actor=self.head_user)
        self.assertFalse(FuneralDeskAssignment.objects.filter(funeral_event=self.funeral, user=self.ordinary_user).exists())

    def test_family_head_cannot_remove_a_community_desk_assignment(self):
        funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.chairman, desk_type="community", user=self.ordinary_user)
        with self.assertRaises(ValidationError):
            funeral_services.remove_desk_worker(funeral=self.funeral, user=self.ordinary_user, actor=self.head_user)

    def test_assigning_the_same_user_twice_updates_rather_than_duplicates(self):
        funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.chairman, desk_type="community", user=self.ordinary_user)
        funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.chairman, desk_type="elders", user=self.ordinary_user)
        self.assertEqual(FuneralDeskAssignment.objects.filter(funeral_event=self.funeral, user=self.ordinary_user).count(), 1)
        assignment = FuneralDeskAssignment.objects.get(funeral_event=self.funeral, user=self.ordinary_user)
        self.assertEqual(assignment.desk_type, "elders")

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client


class DeskAssignmentHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chairman = User.objects.create_user(username="chairman2", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.head_member = member_services.register_member(community=self.bodi, full_name="The Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="the_head2", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_chairman_can_create_a_brand_new_guest_desk_worker_account_via_http(self):
        client = self._login("chairman2")
        res = client.post(f"/api/funerals/{self.funeral.id}/desk-assignments/", {
            "new_username": "friend_at_desk", "new_password": "a-real-password-123", "desk_type": "guest",
        })
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["desk_type"], "guest")

    def test_family_head_cannot_create_a_guest_desk_via_http(self):
        client = self._login("the_head2")
        res = client.post(f"/api/funerals/{self.funeral.id}/desk-assignments/", {
            "new_username": "shouldnt_work", "new_password": "a-real-password-123", "desk_type": "guest",
        })
        self.assertEqual(res.status_code, 400)

    def test_list_desk_assignments_via_http(self):
        client = self._login("chairman2")
        client.post(f"/api/funerals/{self.funeral.id}/desk-assignments/", {
            "new_username": "friend_at_desk2", "new_password": "a-real-password-123", "desk_type": "elders",
        })
        res = client.get(f"/api/funerals/{self.funeral.id}/desk-assignments/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["desk_type"], "elders")

    def test_remove_desk_assignment_via_http(self):
        client = self._login("chairman2")
        create_res = client.post(f"/api/funerals/{self.funeral.id}/desk-assignments/", {
            "new_username": "friend_at_desk3", "new_password": "a-real-password-123", "desk_type": "community",
        })
        assignment_id = create_res.data["id"]
        delete_res = client.delete(f"/api/funerals/{self.funeral.id}/desk-assignments/{assignment_id}/")
        self.assertEqual(delete_res.status_code, 204)
        self.assertEqual(FuneralDeskAssignment.objects.filter(id=assignment_id).count(), 0)

    def test_the_funeral_itself_still_cannot_be_deleted_even_though_delete_is_now_enabled(self):
        client = self._login("admin")
        res = client.delete(f"/api/funerals/{self.funeral.id}/")
        self.assertEqual(res.status_code, 405)
        self.assertTrue(FuneralEvent.objects.filter(id=self.funeral.id).exists())


class FamilyDeskApprovalWorkflowTests(TestCase):
    """
    'Only the abusuapanin of each family can assign someone as a front
    desk officer or collector and it has to be approved by the
    community admin or temporary admin.'
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-desk-approval",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="desk_approval_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.other_admin = User.objects.create_user(username="desk_approval_other_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.head_member = member_services.register_member(community=self.bodi, full_name="Desk Approval Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="desk_approval_head", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)

        self.secretary_member = member_services.register_member(community=self.bodi, full_name="Desk Approval Secretary", gender="female", family=self.asona)
        self.secretary_user = User.objects.create_user(username="desk_approval_secretary", password="x", community=self.bodi, role=Role.FAMILY_SECRETARY)
        member_services.link_member_to_user(member=self.secretary_member, user=self.secretary_user, actor=self.admin)
        self.asona.family_secretary = self.secretary_member
        self.asona.save(update_fields=["family_secretary"])

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Desk Approval Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        self.recruit = User.objects.create_user(username="desk_approval_recruit", password="x", community=self.bodi, role=Role.COMMUNITY_MEMBER)

    def test_the_family_head_assigning_a_family_desk_starts_inactive(self):
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.head_user, desk_type="family", user=self.recruit)
        self.assertFalse(assignment.is_active)

    def test_a_pending_family_desk_assignment_grants_no_real_access_yet(self):
        funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.head_user, desk_type="family", user=self.recruit)
        obligation = ContributionObligation.objects.filter(funeral_event=self.funeral, member=self.head_member).first()
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "desk_approval_recruit", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(f"/api/funerals/{self.funeral.id}/obligations/{obligation.id}/record-payment/", {"amount": "50", "method": "cash"})
        self.assertEqual(res.status_code, 403)

    def test_family_secretary_can_no_longer_open_a_family_desk(self):
        """A real narrowing, not a regression to preserve — only the abusuapanin now, per the spec."""
        with self.assertRaises(ValidationError):
            funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.secretary_user, desk_type="family", user=self.recruit)

    def test_community_admin_approving_activates_the_assignment_and_grants_real_access(self):
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.head_user, desk_type="family", user=self.recruit)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.admin)
        assignment.refresh_from_db()
        self.assertTrue(assignment.is_active)

        obligation = ContributionObligation.objects.filter(funeral_event=self.funeral, member=self.head_member).first()
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "desk_approval_recruit", "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        res = client.post(f"/api/funerals/{self.funeral.id}/obligations/{obligation.id}/record-payment/", {"amount": "50", "method": "cash"})
        self.assertEqual(res.status_code, 201)

    def test_a_community_admin_opening_a_family_desk_directly_is_immediately_active(self):
        """That authority already IS the approval — no separate sign-off needed from itself."""
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.admin, desk_type="family", user=self.recruit)
        self.assertTrue(assignment.is_active)

    def test_pending_desk_assignments_appear_in_the_community_admins_own_queue(self):
        funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.head_user, desk_type="family", user=self.recruit)
        pending = funeral_services.list_pending_desk_assignments(self.bodi)
        self.assertEqual(pending.count(), 1)

    def test_an_approved_assignment_no_longer_appears_in_the_pending_queue(self):
        assignment = funeral_services.assign_desk_worker(funeral=self.funeral, actor=self.head_user, desk_type="family", user=self.recruit)
        funeral_services.approve_desk_assignment(assignment=assignment, actor=self.admin)
        pending = funeral_services.list_pending_desk_assignments(self.bodi)
        self.assertEqual(pending.count(), 0)

    def test_the_full_http_round_trip_via_the_pending_and_approve_endpoints(self):
        head_client = APIClient()
        login = head_client.post("/api/auth/login/", {"username": "desk_approval_head", "password": "a-real-password-123"})
        head_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        assign_res = head_client.post(f"/api/funerals/{self.funeral.id}/desk-assignments/", {"desk_type": "family", "user_id": str(self.recruit.id)})
        self.assertEqual(assign_res.status_code, 201)
        self.assertFalse(assign_res.data["is_active"])

        admin_client = APIClient()
        login = admin_client.post("/api/auth/login/", {"username": "desk_approval_admin", "password": "a-real-password-123"})
        admin_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        pending_res = admin_client.get("/api/desk-assignments/pending/")
        self.assertEqual(pending_res.status_code, 200)
        self.assertEqual(len(pending_res.data), 1)

        approve_res = admin_client.post(f"/api/desk-assignments/{assign_res.data['id']}/approve/")
        self.assertEqual(approve_res.status_code, 200)
        self.assertTrue(approve_res.data["is_active"])
