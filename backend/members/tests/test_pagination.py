from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from tenants.models import Community


class MemberListPaginationTests(TestCase):
    """
    Proves pagination actually happens on a real request/response cycle,
    not just that PAGE_SIZE is set in settings.py — 30 members created,
    default page size is 25, so page 1 must come back with exactly 25
    results, a real `next` link, and an accurate total `count`.
    """

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        for i in range(30):
            member_services.register_member(community=self.bodi, full_name=f"Member {i:02d}", gender="male", family=self.asona)

        self.client = APIClient()
        login = self.client.post("/api/auth/login/", {"username": "admin", "password": "x"})
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")

    def test_first_page_returns_25_with_a_next_link_and_correct_count(self):
        res = self.client.get("/api/members/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 30)
        self.assertEqual(len(res.data["results"]), 25)
        self.assertIsNotNone(res.data["next"])
        self.assertIsNone(res.data["previous"])

    def test_second_page_returns_the_remaining_5(self):
        res = self.client.get("/api/members/?page=2")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["results"]), 5)
        self.assertIsNotNone(res.data["previous"])
        self.assertIsNone(res.data["next"])
