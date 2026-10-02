from django.db import migrations

MEMBER_ROLES = {"community_member", "guest"}


def executives_move_to_the_executive_login(apps, schema_editor):
    """
    'Build a separate member login per person, and member accounts play no other roles.' Until now a person had
    ONE login, and giving them an office changed that login's role. From now on a member's login is always a
    member, and an office lives on a separate executive login. So every existing login that holds an office is
    an EXECUTIVE login: it moves from `linked_user` to `executive_login`. The person keeps that login and its
    powers exactly as before; what they do not yet have is a member login — created on request (their own, from
    the executive dashboard, or by whoever manages them). Logins that are plain members stay where they are.
    """
    Member = apps.get_model("members", "Member")
    for member in Member.objects.exclude(linked_user__isnull=True).select_related("linked_user"):
        if member.linked_user.role not in MEMBER_ROLES:
            member.executive_login = member.linked_user
            member.linked_user = None
            member.save(update_fields=["executive_login", "linked_user"])


class Migration(migrations.Migration):
    dependencies = [("members", "0013_member_executive_login")]
    operations = [migrations.RunPython(executives_move_to_the_executive_login, migrations.RunPython.noop)]
