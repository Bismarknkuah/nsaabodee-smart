from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import Role, User
from families import services
from families.models import Family, FamilyAuditLog
from members.models import Member
from tenants.models import Community


class FamilyServiceTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.other = Community.objects.create(name="Some Other Community", slug="other")
        self.admin = User.objects.create_user(
            username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN
        )

    def test_create_family(self):
        family = services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        self.assertEqual(family.status, Family.Status.ACTIVE)
        self.assertEqual(family.slug, "asona")
        self.assertEqual(FamilyAuditLog.objects.filter(action="created").count(), 1)

    def test_cannot_create_duplicate_active_family_in_same_community(self):
        services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        with self.assertRaises(ValidationError):
            services.create_family(community=self.bodi, name="asona", actor=self.admin)  # case-insensitive

    def test_same_family_name_allowed_across_different_communities(self):
        f1 = services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        f2 = services.create_family(community=self.other, name="Asona", actor=self.admin)
        self.assertNotEqual(f1.community_id, f2.community_id)

    def test_rename_family(self):
        family = services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        renamed = services.rename_family(family=family, new_name="Asona Royal", actor=self.admin)
        self.assertEqual(renamed.name, "Asona Royal")
        self.assertTrue(FamilyAuditLog.objects.filter(action="renamed", family=family).exists())

    def test_merge_moves_members_and_marks_source_merged(self):
        asona = services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        bretuo = services.create_family(community=self.bodi, name="Bretuo", actor=self.admin)
        m1 = Member.objects.create(community=self.bodi, family=bretuo, full_name="Kofi", gender="male")
        m2 = Member.objects.create(community=self.bodi, family=bretuo, full_name="Ama", gender="female")

        services.merge_families(source=bretuo, target=asona, actor=self.admin)

        bretuo.refresh_from_db()
        m1.refresh_from_db()
        m2.refresh_from_db()

        self.assertEqual(bretuo.status, Family.Status.MERGED)
        self.assertEqual(bretuo.merged_into_id, asona.id)
        self.assertEqual(m1.family_id, asona.id)
        self.assertEqual(m2.family_id, asona.id)

    def test_cannot_merge_across_communities(self):
        f1 = services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        f2 = services.create_family(community=self.other, name="Asona", actor=self.admin)
        with self.assertRaises(ValidationError):
            services.merge_families(source=f1, target=f2, actor=self.admin)

    def test_deactivate_then_reactivate(self):
        family = services.create_family(community=self.bodi, name="Oyoko", actor=self.admin)
        services.deactivate_family(family=family, actor=self.admin)
        family.refresh_from_db()
        self.assertEqual(family.status, Family.Status.DEACTIVATED)

        services.reactivate_family(family=family, actor=self.admin)
        family.refresh_from_db()
        self.assertEqual(family.status, Family.Status.ACTIVE)

    def test_delete_blocked_when_family_has_active_members(self):
        family = services.create_family(community=self.bodi, name="Agona", actor=self.admin)
        Member.objects.create(community=self.bodi, family=family, full_name="Yaw", gender="male")
        with self.assertRaises(ValidationError):
            services.delete_family(family=family, actor=self.admin)

    def test_force_delete_orphans_members_instead_of_deleting_them(self):
        family = services.create_family(community=self.bodi, name="Agona", actor=self.admin)
        member = Member.objects.create(community=self.bodi, family=family, full_name="Yaw", gender="male")
        services.delete_family(family=family, actor=self.admin, force=True)
        member.refresh_from_db()
        self.assertIsNone(member.family)
        family.refresh_from_db()
        self.assertEqual(family.status, Family.Status.DELETED)

    def test_transfer_members(self):
        asenie = services.create_family(community=self.bodi, name="Asenie", actor=self.admin)
        ekuona = services.create_family(community=self.bodi, name="Ekuona", actor=self.admin)
        m = Member.objects.create(community=self.bodi, family=asenie, full_name="Abena", gender="female")

        services.transfer_members(member_ids=[m.id], target_family=ekuona, actor=self.admin)
        m.refresh_from_db()
        self.assertEqual(m.family_id, ekuona.id)
        self.assertTrue(
            FamilyAuditLog.objects.filter(action="member_transferred_in", family=ekuona).exists()
        )

    def test_assign_family_head_requires_membership(self):
        family = services.create_family(community=self.bodi, name="Asakyiri", actor=self.admin)
        outsider = Member.objects.create(community=self.bodi, family=None, full_name="Kojo", gender="male")
        with self.assertRaises(ValidationError):
            services.assign_family_head(family=family, member=outsider, actor=self.admin)

        insider = Member.objects.create(community=self.bodi, family=family, full_name="Efua", gender="female")
        updated = services.assign_family_head(family=family, member=insider, actor=self.admin)
        self.assertEqual(updated.family_head_id, insider.id)
