from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from tenants.models import Community


class TownEldersOfficerLedgerAccessTests(TestCase):
    """The two Town-Elders officer roles run their part of exactly this ledger, so they can read it; a plain member still cannot."""

    def _client(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_the_arrears_officer_can_read_the_ledger_but_the_registration_officer_and_a_member_cannot(self):
        """'The registration officer is not allowed to see the financial oversight' — the ledger is money, so only the arrears officer among the two."""
        bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="teola-bodi")
        arrears = User.objects.create_user(username="teola_arrears", password="x", community=bodi, role=Role.TOWN_ELDERS_ARREARS_OFFICER)
        self.assertEqual(self._client(arrears).get("/api/reports/town-elders-ledger/").status_code, 200)
        registrar = User.objects.create_user(username="teola_registrar", password="x", community=bodi, role=Role.TOWN_REGISTRATION_OFFICER)
        self.assertEqual(self._client(registrar).get("/api/reports/town-elders-ledger/").status_code, 403)
        member = User.objects.create_user(username="teola_member", password="x", community=bodi, role=Role.COMMUNITY_MEMBER)
        self.assertEqual(self._client(member).get("/api/reports/town-elders-ledger/").status_code, 403)
