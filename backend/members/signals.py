"""
"Every member is automatically registered in the ledger" is enforced here,
not as a manual step anyone has to remember: the instant a new active
Member row is saved, they're fanned out into every currently-open
funeral's contribution ledger at whichever rate (own-family or general)
applies to them.
"""


def enroll_new_member_in_open_funerals(sender, instance, created, **kwargs):
    if not created:
        return
    from funerals.services import enroll_new_member_in_open_funerals as enroll
    enroll(instance)
