"""
Seeds the Sefwi Bodi community with the families named in the master spec.

This is exactly the customization the module is designed for: the platform
code has ZERO hardcoded family names anywhere — Bodi's families are pure
data, loaded here as an optional convenience seed. Any other community
adopting Nsaabodeɛ Smart runs its own seed (or just uses the Add Family
screen) with its own family names and owes nothing to this file.

Usage:
    python manage.py seed_bodi_families
"""

from django.core.management.base import BaseCommand

from families import services
from tenants.models import Community

BODI_FAMILIES = [
    "Asona",
    "Bretuo",
    "Aduana",
    "Oyoko",
    "Asakyiri",
    "Asenie",
    "Ekuona",
    "Agona",
]


class Command(BaseCommand):
    help = "Seed the standard Sefwi Bodi families for the Bodi Anidasoɔ Funeral Management System."

    def add_arguments(self, parser):
        parser.add_argument("--community-slug", default="bodi-anidasoq")

    def handle(self, *args, **options):
        community, _ = Community.objects.get_or_create(
            slug=options["community_slug"],
            defaults={"name": "Bodi Anidasoɔ Funeral Management System", "region": "Sefwi Bodi"},
        )
        created = 0
        for name in BODI_FAMILIES:
            try:
                services.create_family(community=community, name=name, actor=None)
                created += 1
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"Skipped '{name}': {exc}"))
        self.stdout.write(self.style.SUCCESS(f"Seeded {created} families for {community.name}."))
