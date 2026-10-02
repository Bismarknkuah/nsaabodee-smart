import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("tenants", "0020_community_subscription_plan")]

    operations = [
        migrations.CreateModel(
            name="SubscriptionPlan",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("code", models.SlugField(max_length=40, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("description", models.TextField(blank=True)),
                ("price_yearly", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("price_monthly", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("max_members", models.PositiveIntegerField(blank=True, help_text="Null means unlimited.", null=True)),
                ("max_communities", models.PositiveSmallIntegerField(default=1)),
                ("trial_days", models.PositiveSmallIntegerField(default=0)),
                ("features", models.JSONField(blank=True, default=list)),
                ("is_active", models.BooleanField(default=True)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["sort_order", "name"]},
        ),
        migrations.AddField(
            model_name="community",
            name="plan",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="communities", to="tenants.subscriptionplan"),
        ),
    ]
