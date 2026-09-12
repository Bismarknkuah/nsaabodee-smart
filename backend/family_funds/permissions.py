from rest_framework.permissions import BasePermission


class CanAccessFamilyFund(BasePermission):
    """
    "One family head shouldn't get access to other families' activities."
    Restricted to THIS family's own head/secretary/treasurer, or
    Community Admin+/superuser — never the general funeral committee,
    never another family's officers. The family is resolved in the view
    (from the URL) and checked via families.services.is_family_officer.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)
