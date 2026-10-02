from django.db import migrations

CONSOLIDATION = {
    "arrears_collector": ("collector", None),
    "family_arrears_officer": ("collector", "family"),
    "town_elders_arrears_officer": ("collector", "town_elder"),
    "notification_officer": ("secretary", None),
    "community_registration_desk": ("secretary", None),
    "treasurer": ("financial_secretary", None),
    # NOT merged: an Auditor is read-only oversight and never records or approves.
    # Financial Secretary can record expenses and decide statuses, so folding an
    # Auditor into it would silently GRANT those powers. Existing auditors keep the
    # legacy `auditor` value (still fully supported, read-only) until a decision is
    # made about how to represent a read-only auditor in the consolidated model.
}


def forwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    Member = apps.get_model("members", "Member")
    CollectorNomination = apps.get_model("members", "CollectorNomination")
    for user in User.objects.filter(role__in=list(CONSOLIDATION)):
        new_role, nomination_type = CONSOLIDATION[user.role]
        old = user.role
        user.role = new_role
        user.save(update_fields=["role"])
        if nomination_type:
            # A family or Town-Elders arrears officer becomes a collector whose
            # jurisdiction is carried by an approved nomination of that type.
            member = Member.objects.filter(linked_user=user).first()
            if member is not None:
                scoped_family = member.family if nomination_type == "family" else None
                if nomination_type == "family" and scoped_family is None:
                    continue
                exists = CollectorNomination.objects.filter(member=member, collector_type=nomination_type, status="approved").exists()
                if not exists:
                    CollectorNomination.objects.create(
                        community=member.community, member=member, collector_type=nomination_type,
                        scoped_family=scoped_family, status="approved",
                    )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0013_alter_user_role"), ("members", "0012_member_father_name_member_hometown_and_more")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
