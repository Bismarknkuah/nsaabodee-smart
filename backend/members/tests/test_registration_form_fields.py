from django.test import TestCase
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from members import services as member_services
from members.models import Member
from tenants.models import Community


class RegistrationFormFieldsTests(TestCase):
    """'The registration form should be redesigned to ask more information about the person mother father background and many more.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="rff-bodi")
        self.admin = User.objects.create_user(username="rff_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

    def test_registering_with_full_background_information(self):
        member = member_services.register_member(
            community=self.bodi, full_name="Kwame Mensah", gender="male", family=self.asona,
            mother_name="Akosua Mensah", father_name="Kofi Mensah", hometown="Kumasi",
            marital_status=Member.MaritalStatus.MARRIED, spouse_name="Ama Mensah",
        )
        self.assertEqual(member.mother_name, "Akosua Mensah")
        self.assertEqual(member.father_name, "Kofi Mensah")
        self.assertEqual(member.hometown, "Kumasi")
        self.assertEqual(member.marital_status, "married")
        self.assertEqual(member.spouse_name, "Ama Mensah")

    def test_registering_with_none_of_the_new_fields_still_works(self):
        """Every new field is optional — existing registration flows are completely unaffected."""
        member = member_services.register_member(community=self.bodi, full_name="Plain Registration", gender="male", family=self.asona)
        self.assertEqual(member.mother_name, "")
        self.assertEqual(member.marital_status, "")

    def test_updating_an_existing_member_with_background_information(self):
        member = member_services.register_member(community=self.bodi, full_name="Existing Member", gender="male", family=self.asona)
        member_services.update_member(member=member, mother_name="Efua", father_name="Yaw", hometown="Cape Coast")
        member.refresh_from_db()
        self.assertEqual(member.mother_name, "Efua")
        self.assertEqual(member.hometown, "Cape Coast")


class RegistrationFormFieldsHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="rffh-bodi")
        self.admin = User.objects.create_user(username="rffh_admin", password="a-real-password-123", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)

    def _login(self, username):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": username, "password": "a-real-password-123"})
        self.assertEqual(login.status_code, 200, login.data)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_full_http_registration_with_background_fields(self):
        client = self._login("rffh_admin")
        res = client.post(
            "/api/members/",
            {
                "full_name": "Yaw Boateng", "gender": "male", "family_id": str(self.asona.id),
                "mother_name": "Adwoa Boateng", "father_name": "Kwabena Boateng",
                "hometown": "Tamale", "marital_status": "single",
            },
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["mother_name"], "Adwoa Boateng")
        self.assertEqual(res.data["hometown"], "Tamale")
