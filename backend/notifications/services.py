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


def send_birthday_messages(*, on_date=None):
    """
    'When someone registered the system should wish them happy
    birthday messages on their birthday.' Runs once daily (see
    notifications.tasks.send_birthday_messages_task and its Celery
    Beat schedule in settings.py) — finds every member whose
    date_of_birth matches today's month and day, regardless of birth
    year, and sends a real, warm notification to their own linked
    account. A member with no login yet (most members never get one)
    simply has nothing to receive this into — not an error, just
    nothing to do for them today.
    """
    from django.utils import timezone

    from members.models import Member

    today = on_date or timezone.localdate()
    birthday_members = Member.objects.filter(
        date_of_birth__month=today.month, date_of_birth__day=today.day,
        status=Member.Status.ACTIVE, linked_user__isnull=False,
    ).select_related("linked_user", "community")

    sent = []
    for member in birthday_members:
        notification = Notification.objects.create(
            community=member.community,
            category=Notification.Category.BIRTHDAY,
            message=f"Happy birthday, {member.full_name.split()[0]}! Wishing you a wonderful day from all of us.",
            recipient_user=member.linked_user,
            related_member=member,
        )
        _deliver(notification)
        sent.append(notification)
    return sent


def notify_eligible_members_of_campaign(*, members, campaign_title, community):
    """
    'Notifications must respect scope' — the recipient list itself
    IS the scope enforcement: callers pass in exactly the same
    eligible-members queryset the campaign already used to generate
    its own obligations (welfare.services._eligible_members_for),
    so a Family A campaign only ever reaches Family A members, and a
    community-wide one reaches everyone eligible community-wide —
    never a separate, second scope decision that could quietly
    disagree with the first.

    Only members with a linked User login are actually notified —
    matching notify_family_head's own established pattern — since a
    Notification needs a real recipient_user or recipient_role to
    ever be seen by anyone.
    """
    sent = []
    for member in members.filter(linked_user__isnull=False).select_related("linked_user"):
        notification = Notification.objects.create(
            community=community,
            category=Notification.Category.WELFARE_CAMPAIGN_LAUNCHED,
            message=f"A new contribution campaign, '{campaign_title}', has started — you're eligible to contribute.",
            recipient_user=member.linked_user,
            related_member=member,
        )
        _deliver(notification)
        sent.append(notification)
    return sent


def notify_community_of_new_announcement(*, community, announcement_title):
    """
    'Members notification should have features where they can see
    what has been posted on the notice board.' Every member of this
    community with a linked login gets notified the moment an
    announcement is actually approved — the same "loop over linked
    members, one Notification each" pattern already established for
    campaign launches, since notice board posts are genuinely
    community-wide, not scoped to any narrower eligibility the way a
    contribution campaign's own members queryset is.
    """
    from members.models import Member

    sent = []
    for member in Member.objects.filter(community=community, linked_user__isnull=False).select_related("linked_user"):
        notification = Notification.objects.create(
            community=community,
            category=Notification.Category.NOTICE_BOARD_POST,
            message=f"A new notice board post — '{announcement_title}' — has just been approved.",
            recipient_user=member.linked_user,
            related_member=member,
        )
        _deliver(notification)
        sent.append(notification)
    return sent
