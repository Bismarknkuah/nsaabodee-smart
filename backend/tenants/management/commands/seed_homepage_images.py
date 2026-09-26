"""
'I have attached photos of some chiefs which you can use on the home
page where they can be changing or flipping randomly.' Idempotent
(get_or_create keyed on caption, matching seed_demo_data.py's own
established convention) — safe to run on every deploy without
duplicating rows if it's ever run twice.

These are the same five images the person themselves supplied for
this exact purpose; nothing here was sourced independently. If a
Platform Admin ever wants to replace or retire one, that's a normal
edit/delete through the existing Homepage Images management screen —
this command only ever seeds them once, on first run.
"""

import os

from django.core.files import File
from django.core.management.base import BaseCommand

from tenants.models import HomepageImage

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "seed_assets", "homepage_photos")

# (filename, caption, subcaption, display_order)
SEED_IMAGES = [
    ("chief_1.jpg", "Nana Kwabena Ebii II", "Chief of Sefwi Akontombra, in state with his elders", 1),
    ("chief_2.jpg", "Chieftaincy & Fellowship", "Traditional leaders in the community", 2),
    ("chief_3.jpg", "Community Heritage", "Traditional leadership and culture", 3),
    ("chief_4.jpg", "Traditional Leadership", "Chiefs and elders in ceremonial state", 4),
    ("chief_5.jpg", "Chieftaincy & Culture", "Preserving the traditions our communities are built on", 5),
]


class Command(BaseCommand):
    help = "Seeds the homepage's rotating carousel with a starting set of chief/community photos, if none exist yet."

    def handle(self, *args, **options):
        created_count = 0
        for filename, caption, subcaption, display_order in SEED_IMAGES:
            if HomepageImage.objects.filter(caption=caption).exists():
                continue
            path = os.path.join(ASSETS_DIR, filename)
            if not os.path.exists(path):
                self.stdout.write(self.style.WARNING(f"Seed asset not found, skipping: {path}"))
                continue
            with open(path, "rb") as f:
                homepage_image = HomepageImage(caption=caption, subcaption=subcaption, display_order=display_order)
                homepage_image.image.save(filename, File(f), save=True)
            created_count += 1
        self.stdout.write(self.style.SUCCESS(f"Seeded {created_count} homepage image(s)."))
