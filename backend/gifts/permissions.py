from rest_framework.permissions import BasePermission

from accounts.models import Role

# Same principle as PAYMENT_COLLECTING_ROLES in funerals/permissions.py
# — narrowed to whoever actually staffs collections, not every
# financial-oversight role.
GIFT_RECORDING_ROLES = {
    Role.COLLECTOR,
}


class CanRecordGifts(BasePermission):
    """Only a collecting role can RECORD a gift — the cashier taking a guest's money."""

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.is_superuser or request.user.role in GIFT_RECORDING_ROLES


class IsSameCommunity(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        return str(obj.community_id) == str(getattr(request.user, "community_id", None))


def is_family_head_of(user, family) -> bool:
    """
    The master brief is explicit: "the funeral committee should have
    access to all the money paid EXCEPT the donations." Ledger 1
    (mandatory contributions) stays visible to the whole committee
    (Treasurer, Financial Secretary, Auditor, etc. — see funerals/reports
    permissions); Ledger 2 (gifts, guests, town leaders, donation
    accounts) does NOT get that same blanket visibility. Only this
    specific family's own head — checked against his own linked Member
    profile, not just "some Family Head somewhere" — or a superuser can
    browse the full gift ledger for one of his family's funerals.
    Everyone else only ever sees their OWN received-donations view (see
    GiftMyDonationsReceivedView), never the whole list.
    """
    member = getattr(user, "member_profile", None)
    return bool(member and family.family_head_id and member.id == family.family_head_id)


class CanViewGiftLedger(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
