from django.db import migrations

# Seeded from the exact three plans the public homepage's own plan
# cards already describe (frontend/src/app/page.tsx) — same names, same
# taglines, same feature lists. Prices deliberately left unset: the
# homepage cards are lead capture with no published pricing.
SEED = [
    {"code": "single_funeral", "name": "Single Funeral", "sort_order": 1, "max_communities": 1,
     "description": "For one family, one event. Short-term access for the funeral's duration.",
     "features": ["Full four-ledger system", "Front desk, cash & MoMo", "Instant receipts", "Access for the funeral's duration"]},
    {"code": "community", "name": "Community", "sort_order": 2, "max_communities": 1,
     "description": "Ongoing, for an established society. Always-on.",
     "features": ["Everything in Single Funeral", "Unlimited concurrent funerals", "All role dashboards", "Offline-capable front desk"]},
    {"code": "multi_community", "name": "Multi-Community", "sort_order": 3, "max_communities": 10,
     "description": "For an organization running several communities. Platform-wide.",
     "features": ["Everything in Community", "Platform Admin oversight console", "Isolated data per community", "Priority support"]},
]


def seed_and_map(apps, schema_editor):
    SubscriptionPlan = apps.get_model("tenants", "SubscriptionPlan")
    Community = apps.get_model("tenants", "Community")
    by_code = {}
    for row in SEED:
        plan, _ = SubscriptionPlan.objects.get_or_create(code=row["code"], defaults=row)
        by_code[row["code"]] = plan
    for community in Community.objects.all():
        code = getattr(community, "subscription_plan", None) or "community"
        community.plan = by_code.get(code, by_code["community"])
        community.save(update_fields=["plan"])


def unmap(apps, schema_editor):
    Community = apps.get_model("tenants", "Community")
    for community in Community.objects.select_related("plan"):
        community.subscription_plan = community.plan.code if community.plan_id else "community"
        community.save(update_fields=["subscription_plan"])


class Migration(migrations.Migration):
    dependencies = [("tenants", "0021_subscriptionplan_and_plan_fk")]
    operations = [migrations.RunPython(seed_and_map, unmap)]
