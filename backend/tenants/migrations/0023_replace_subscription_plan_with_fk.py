from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("tenants", "0022_seed_plans_and_map_communities")]

    operations = [
        migrations.RemoveField(model_name="community", name="subscription_plan"),
        migrations.RenameField(model_name="community", old_name="plan", new_name="subscription_plan"),
    ]
