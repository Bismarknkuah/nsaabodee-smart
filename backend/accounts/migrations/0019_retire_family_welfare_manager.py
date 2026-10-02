from django.db import migrations


def retire_family_welfare_managers(apps, schema_editor):
    """
    "No family will have their personal welfare managers." The office is closed. In the two-login model that means:
    the person's executive login is deactivated if they have a member login; if that executive login is their only
    login it becomes their member login instead, so nobody is locked out.
    """
    User = apps.get_model("accounts", "User")
    Member = apps.get_model("members", "Member")
    for user in User.objects.filter(role="family_welfare_manager"):
        member = Member.objects.filter(executive_login=user).first()
        if member is not None and member.linked_user_id:
            user.is_active = False
            user.custom_role = None
            user.save(update_fields=["is_active", "custom_role"])
            member.executive_login = None
            member.save(update_fields=["executive_login"])
        else:
            user.role = "community_member"
            user.custom_role = None
            user.save(update_fields=["role", "custom_role"])
            if member is not None:
                member.executive_login = None
                member.linked_user = user
                member.save(update_fields=["executive_login", "linked_user"])


class Migration(migrations.Migration):
    dependencies = [("accounts", "0018_retire_guest_role"), ("members", "0014_split_executive_logins")]
    operations = [migrations.RunPython(retire_family_welfare_managers, migrations.RunPython.noop)]
