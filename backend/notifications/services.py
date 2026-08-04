from accounts.models import Role
from .models import Notification


def notify_family_head(*, family, member, message, category=Notification.Category.DEFAULTER_ESCALATION):
    if not family.family_head_id:
        return None
    notification = _notify_family_head(family, member, message, category)
    _deliver(notification)
    return notification


def _notify_family_head(family, member, message, category=Notification.Category.DEFAULTER_ESCALATION):
    """
    If the family's head happens to be linked to a User login
    (members.services.link_member_to_user), target that specific person
    — they're the one who should actually be notified about their own
    family's defaulter, not every Family Head community-wide. Falls back
    to a role-wide broadcast only when no such link exists yet, which is
    still the common case since linking is an admin action, not automatic.
    """
    linked_user = getattr(family.family_head.linked_user, "id", None) and family.family_head.linked_user
    return Notification.objects.create(
        community=family.community,
        category=category,
        message=f"[Family Head, {family.name}] {message}",
        recipient_user=linked_user,
        recipient_role="" if linked_user else Role.FAMILY_HEAD,
        related_member=member,
    )


def notify_treasurers(*, community, member, message):
    notification = Notification.objects.create(
        community=community,
        category=Notification.Category.DEFAULTER_ESCALATION,
        message=f"[Treasurer] {message}",
        recipient_role=Role.TREASURER,
        related_member=member,
    )
    _deliver(notification)
    return notification


def notify_financial_secretary(*, community, member, message):
    notification = Notification.objects.create(
        community=community,
        category=Notification.Category.OLD_DEBT,
        message=f"[Financial Secretary] {message}",
        recipient_role=Role.FINANCIAL_SECRETARY,
        related_member=member,
    )
    _deliver(notification)
    return notification


def notify_old_debt(*, owed_to_family, member, message):
    """
    'Old debts have to be credited to the family the person owes and
    the financial secretary and the family head have to be updated.'
    One call, two recipients: the community's Financial Secretary(ies)
    (role-wide — old debt is a community-level accountability concern,
    not scoped to one family) and specifically the HEAD of the family
    this debt is actually owed to (their own family's money, so they
    get the same targeted-if-linked treatment notify_family_head uses).
    """
    notify_financial_secretary(community=owed_to_family.community, member=member, message=message)
    if owed_to_family.family_head_id:
        notify_family_head(family=owed_to_family, member=member, message=message, category=Notification.Category.OLD_DEBT)


def _deliver(notification):
    """
    Fire-and-record real delivery (console/email/SMS, per
    communication.services.deliver_notification) the instant a
    notification is created — not a separate manual step an
    administrator has to remember to trigger. Goes through Celery
    (see communication/tasks.py) so a slow SMS/WhatsApp provider round
    -trip never blocks whatever request just triggered this notification
    (e.g. a collector recording a payment that happens to push someone
    over the defaulter threshold).
    """
    from communication.tasks import deliver_notification_task
    deliver_notification_task.delay(str(notification.id))
