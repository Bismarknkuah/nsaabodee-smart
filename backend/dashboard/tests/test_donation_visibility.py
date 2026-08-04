from decimal import Decimal

from django.test import TestCase

from accounts.models import Role, User
from dashboard.services import build_dashboard
from families import services as family_services
from funerals import services as funeral_services
from gifts import services as gift_services
from members import services as member_services
from tenants.models import Community


class CommitteeExcludedFromDonationsTests(TestCase):
    """
    'The funeral committee should have access to all the money paid
    except the donations.' Community Admin keeps oversight; Chairman,
    Secretary, Treasurer, Financial Secretary, and Auditor do not see
    gift/donation figures anywhere in their own dashboard.
    """

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.chairman = User.objects.create_user(username="chairman", password="x", community=self.bodi, role=Role.CHAIRMAN)
        self.secretary = User.objects.create_user(username="secretary", password="x", community=self.bodi, role=Role.SECRETARY)
        self.treasurer = User.objects.create_user(username="treasurer", password="x", community=self.bodi, role=Role.TREASURER)

        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        gift_services.record_gift_donation(funeral=self.funeral, donor_name="A Guest", amount_cash=Decimal("500"))

    def test_community_admin_still_sees_gift_cash(self):
        result = build_dashboard(self.admin)
        self.assertIn("gift_cash", result["sections"]["community_overview"]["today_collections"])

    def test_chairman_does_not_see_gift_cash(self):
        result = build_dashboard(self.chairman)
        self.assertNotIn("gift_cash", result["sections"]["community_overview"]["today_collections"])

    def test_secretary_does_not_see_gift_cash(self):
        result = build_dashboard(self.secretary)
        self.assertNotIn("gift_cash", result["sections"]["community_overview"]["today_collections"])

    def test_treasurer_does_not_see_gift_cash(self):
        result = build_dashboard(self.treasurer)
        self.assertNotIn("gift_cash", result["sections"]["financial_overview"]["today"])
        self.assertNotIn("gift_cash", result["sections"]["financial_overview"]["month_to_date"])

    def test_combined_cash_position_excludes_gifts_for_treasurer_but_includes_for_admin(self):
        admin_result = build_dashboard(self.admin)
        treasurer_result = build_dashboard(self.treasurer)

        admin_combined = admin_result["sections"]["community_overview"]["today_collections"]["combined_cash_position_by_method"]
        treasurer_combined = treasurer_result["sections"]["financial_overview"]["today"]["combined_cash_position_by_method"]

        # Admin's combined cash includes the GH₵500 gift; Treasurer's doesn't.
        self.assertEqual(Decimal(admin_combined["cash"]), Decimal("500"))
        self.assertEqual(Decimal(treasurer_combined["cash"]), Decimal("0"))
