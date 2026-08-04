from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from funerals.models import ContributionObligation
from gifts import services as gift_services
from members import services as member_services
from reports import services
from tenants.models import Community


class FuneralDailyBreakdownTests(TestCase):
    """'It starts Friday and closes Sunday evening but they should be able to know the amount they received each day.'"""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.treasurer = User.objects.create_user(username="treasurer", password="x", community=self.bodi, role=Role.TREASURER)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)

        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01",
            collection_start_date="2026-07-03", collection_end_date="2026-07-05",  # Friday to Sunday
            actor=self.admin, own_family_amount=Decimal("50"),
        )
        self.obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)

    def test_every_day_in_the_window_appears_even_with_zero_collections(self):
        breakdown = services.funeral_daily_breakdown(self.funeral)
        self.assertEqual(len(breakdown["days"]), 3)  # Friday, Saturday, Sunday
        self.assertEqual(breakdown["days"][1]["combined_total"], "0")  # quiet Saturday

    def test_a_payment_shows_up_on_the_correct_day_only(self):
        payment = funeral_services.record_payment(obligation=self.obligation, amount=Decimal("50"), method="cash")
        payment.paid_at = timezone.make_aware(timezone.datetime(2026, 7, 3, 10, 0))
        payment.save(update_fields=["paid_at"])

        breakdown = services.funeral_daily_breakdown(self.funeral)
        self.assertEqual(breakdown["days"][0]["date"], "2026-07-03")
        self.assertEqual(Decimal(breakdown["days"][0]["contributions_total"]), Decimal("50"))
        self.assertEqual(Decimal(breakdown["days"][1]["contributions_total"]), Decimal("0"))

    def test_gifts_and_contributions_combine_into_the_day_total(self):
        payment = funeral_services.record_payment(obligation=self.obligation, amount=Decimal("50"), method="cash")
        payment.paid_at = timezone.make_aware(timezone.datetime(2026, 7, 4, 9, 0))
        payment.save(update_fields=["paid_at"])
        gift = gift_services.record_gift_donation(funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("20"))
        gift.given_at = timezone.make_aware(timezone.datetime(2026, 7, 4, 15, 0))
        gift.save(update_fields=["given_at"])

        breakdown = services.funeral_daily_breakdown(self.funeral)
        saturday = breakdown["days"][1]
        self.assertEqual(Decimal(saturday["combined_total"]), Decimal("70"))

    def test_grand_total_sums_every_day(self):
        payment = funeral_services.record_payment(obligation=self.obligation, amount=Decimal("50"), method="cash")
        payment.paid_at = timezone.make_aware(timezone.datetime(2026, 7, 5, 18, 0))
        payment.save(update_fields=["paid_at"])
        breakdown = services.funeral_daily_breakdown(self.funeral)
        self.assertEqual(Decimal(breakdown["grand_total"]), Decimal("50"))

    def test_committee_role_gets_contributions_only_no_gifts_in_daily_breakdown(self):
        gift = gift_services.record_gift_donation(funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("20"))
        gift.given_at = timezone.make_aware(timezone.datetime(2026, 7, 3, 12, 0))
        gift.save(update_fields=["given_at"])

        breakdown = services.funeral_daily_breakdown(self.funeral, include_gift_cash=False)
        self.assertNotIn("gifts_total", breakdown["days"][0])
        self.assertEqual(Decimal(breakdown["days"][0]["combined_total"]), Decimal("0"))  # gift excluded entirely

    def test_http_treasurer_gets_no_gift_figures_admin_does(self):
        gift = gift_services.record_gift_donation(funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("20"))
        gift.given_at = timezone.make_aware(timezone.datetime(2026, 7, 3, 12, 0))
        gift.save(update_fields=["given_at"])

        admin_client = self._login("admin")
        admin_res = admin_client.get(f"/api/reports/funerals/{self.funeral.id}/daily-breakdown/")
        self.assertIn("gifts_total", admin_res.data["days"][0])

        treasurer_client = self._login("treasurer")
        treasurer_res = treasurer_client.get(f"/api/reports/funerals/{self.funeral.id}/daily-breakdown/")
        self.assertNotIn("gifts_total", treasurer_res.data["days"][0])

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "x"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client
