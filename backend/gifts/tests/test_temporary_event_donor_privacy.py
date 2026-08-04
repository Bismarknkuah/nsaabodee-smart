from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from gifts import services as gift_services
from tenants.models import Community


class TemporaryEventDetectionTests(TestCase):
    """'Individuals or organizations renting the platform for temporary use.'"""

    def test_an_ongoing_community_is_never_a_temporary_event(self):
        community = Community.objects.create(name="Permanent Town", slug="permanent-town-privacy")
        self.assertFalse(community.is_temporary_event)

    def test_a_time_limited_community_is_a_temporary_event(self):
        from django.utils import timezone
        from datetime import timedelta
        community = Community.objects.create(
            name="Rented Town", slug="rented-town-privacy",
            access_plan=Community.AccessPlan.TIME_LIMITED, access_expires_at=timezone.now() + timedelta(days=30),
        )
        self.assertTrue(community.is_temporary_event)

    def test_a_single_funeral_community_is_a_temporary_event(self):
        from django.utils import timezone
        from datetime import timedelta
        community = Community.objects.create(
            name="Single Event Town", slug="single-event-town-privacy",
            access_plan=Community.AccessPlan.SINGLE_FUNERAL, access_expires_at=timezone.now() + timedelta(days=7),
        )
        self.assertTrue(community.is_temporary_event)


class DonorPrivacyMaskingHttpTests(TestCase):
    """
    'They must not have access to the private information of individuals
    who register solely to make gift donations unless that information
    is required for reconciliation, auditing, or legal compliance.'
    """

    def setUp(self):
        from django.utils import timezone
        from datetime import timedelta

        self.temp_community = Community.objects.create(
            name="Rented Event", slug="rented-event-donor-privacy",
            access_plan=Community.AccessPlan.TIME_LIMITED, access_expires_at=timezone.now() + timedelta(days=30),
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.temp_admin = User.objects.create_user(username="temp_event_admin", password="a-real-password-123", community=self.temp_community, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.temp_community, name="Asona", actor=self.temp_admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.temp_community, deceased_name="Privacy Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.temp_admin, own_family_amount=Decimal("50"),
        )
        gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="Real Donor Name", donor_phone="0244000000",
            donor_hometown="Kumasi", amount_cash=Decimal("200"),
        )

        self.permanent_community = Community.objects.create(
            name="Permanent Comparison Town", slug="permanent-comparison-donor-privacy",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.permanent_admin = User.objects.create_user(username="permanent_comparison_admin", password="a-real-password-123", community=self.permanent_community, role=Role.COMMUNITY_ADMIN)
        self.permanent_asona = family_services.create_family(community=self.permanent_community, name="Asona", actor=self.permanent_admin)
        self.permanent_funeral = funeral_services.create_funeral_event(
            community=self.permanent_community, deceased_name="Permanent Deceased", deceased_gender="male",
            deceased_family=self.permanent_asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
            actor=self.permanent_admin, own_family_amount=Decimal("50"),
        )
        gift_services.record_gift_donation(
            funeral=self.permanent_funeral, donor_name="Permanent Real Name", donor_phone="0255000000",
            amount_cash=Decimal("150"),
        )

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_a_temporary_events_community_admin_sees_masked_donor_name(self):
        client = self._login("temp_event_admin")
        res = client.get(f"/api/funerals/{self.funeral.id}/gifts/")
        self.assertEqual(res.status_code, 200)
        donation = res.data["results"][0]
        self.assertNotEqual(donation["donor_name"], "Real Donor Name")
        self.assertTrue(donation["donor_name"].startswith("Donor #"))

    def test_masked_donor_phone_and_hometown_are_genuinely_empty(self):
        client = self._login("temp_event_admin")
        res = client.get(f"/api/funerals/{self.funeral.id}/gifts/")
        donation = res.data["results"][0]
        self.assertEqual(donation["donor_phone"], "")
        self.assertEqual(donation["donor_hometown"], "")

    def test_the_real_donation_amount_is_never_hidden_even_when_masked(self):
        """'Monitor collections. View financial summaries.' — the money itself must still be real and accurate."""
        client = self._login("temp_event_admin")
        res = client.get(f"/api/funerals/{self.funeral.id}/gifts/")
        donation = res.data["results"][0]
        self.assertEqual(Decimal(donation["total_value"]), Decimal("200"))

    def test_a_permanent_communitys_admin_is_never_masked(self):
        """No regression — an ordinary, established community's own admin keeps exactly the access they had before."""
        client = self._login("permanent_comparison_admin")
        res = client.get(f"/api/funerals/{self.permanent_funeral.id}/gifts/")
        donation = res.data["results"][0]
        self.assertEqual(donation["donor_name"], "Permanent Real Name")

    def test_the_reconciliation_endpoint_requires_a_stated_reason(self):
        client = self._login("temp_event_admin")
        res = client.get(f"/api/funerals/{self.funeral.id}/gifts/reconciliation/")
        self.assertEqual(res.status_code, 400)

    def test_the_reconciliation_endpoint_reveals_full_donor_detail_with_a_reason(self):
        client = self._login("temp_event_admin")
        res = client.get(f"/api/funerals/{self.funeral.id}/gifts/reconciliation/?reason=Monthly+audit+reconciliation")
        self.assertEqual(res.status_code, 200)
        donation = res.data["results"][0]
        self.assertEqual(donation["donor_name"], "Real Donor Name")

    def test_accessing_reconciliation_writes_a_real_audit_log_entry(self):
        client = self._login("temp_event_admin")
        client.get(f"/api/funerals/{self.funeral.id}/gifts/reconciliation/?reason=Legal+compliance+request")
        from audit_log.models import AuditLogEntry
        entry = AuditLogEntry.objects.filter(action="donor_pii_reconciliation_access", community=self.temp_community).first()
        self.assertIsNotNone(entry)
        self.assertIn("Legal compliance request", entry.description)

    def test_two_donations_from_the_same_donor_get_the_same_anonymous_label(self):
        gift_services.record_gift_donation(
            funeral=self.funeral, donor_name="Real Donor Name", donor_phone="0244000000", amount_cash=Decimal("50"),
        )
        client = self._login("temp_event_admin")
        res = client.get(f"/api/funerals/{self.funeral.id}/gifts/")
        labels = {d["donor_name"] for d in res.data["results"]}
        self.assertEqual(len(labels), 1)
