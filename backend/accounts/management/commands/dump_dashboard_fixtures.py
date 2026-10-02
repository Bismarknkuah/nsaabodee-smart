"""
Dump every demo persona's real /api/dashboard/ payload to a JSON file.

The frontend's render tests feed each dashboard page the REAL shape of its data — the one bug class
TypeScript cannot catch is a page that type-checks and then throws when real data arrives (it has
happened: five roles crashed on a field that was genuinely absent for them). Regenerate after the API
changes:

    python manage.py seed_demo_data
    python manage.py dump_dashboard_fixtures ../frontend/src/__tests__/fixtures/dashboards.json
"""
import json

from django.core.management.base import BaseCommand
from rest_framework.test import APIClient

from accounts.models import VISIBLE_ROLES
from accounts.views import DEMO_PERSONA_USERNAMES


class Command(BaseCommand):
    help = "Write each demo persona's real dashboard payload to a JSON file (for the frontend's render tests)."

    def add_arguments(self, parser):
        parser.add_argument("path")

    def handle(self, *args, path, **options):
        out = {}
        for persona in [*VISIBLE_ROLES, *DEMO_PERSONA_USERNAMES]:
            client = APIClient()
            res = client.post("/api/auth/demo-login/", {"role": persona})
            if res.status_code != 200:
                self.stderr.write(f"skipped {persona}: demo login {res.status_code}")
                continue
            client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
            dash = client.get("/api/dashboard/")
            me = client.get("/api/auth/me/")
            out[persona] = {"role": me.data.get("role"), "dashboard": dash.data}
        with open(path, "w") as f:
            json.dump(out, f, indent=1, default=str, sort_keys=True)
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(out)} personas to {path}"))
