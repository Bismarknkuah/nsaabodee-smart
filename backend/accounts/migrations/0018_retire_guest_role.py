from django.db import migrations


def guests_become_community_members(apps, schema_editor):
    """
    "Remove the guest user role." A guest login is not deleted — that would be data loss for something the
    person may still use — it becomes an ordinary community member. Guests had no member record, so their
    dashboard says "No member profile linked yet" until one is registered for them, and they hold no powers.
    (A guest could also be a throwaway desk-worker account; desk work is now for collectors only, so any such
    assignment simply stops granting anything.)
    """
    User = apps.get_model("accounts", "User")
    User.objects.filter(role="guest").update(role="community_member")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0017_community_member_is_the_default_role")]
    operations = [migrations.RunPython(guests_become_community_members, migrations.RunPython.noop)]
