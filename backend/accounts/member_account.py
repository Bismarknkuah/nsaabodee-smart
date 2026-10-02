"""
The community-member account.

"The member account and personal account is the same user role type... none of the community member
dashboard should be allowed to play any other roles." An executive who switches to their personal
dashboard IS a community member for as long as they are there: every request they make is authorised as
`community_member`, so no endpoint can be reached "as" the executive, whichever way it checks (role sets,
jurisdiction, permission classes) — one choke point instead of a guard on each of hundreds of views.

Two safety properties matter, because this object stands in for a real user row:

  * it is a COPY, and its save() can never write the downgraded role back — a stray `user.save()` deep in
    some service must not be able to demote an executive for good;
  * `real_role` still answers with the account's own role, which is how the switch back to the executive
    dashboard, /me, and the audit log keep telling the truth.
"""
import copy

from .models import DashboardContext, Role

_PROTECTED = {"role", "custom_role", "custom_role_id"}


def as_member_account(user):
    view = copy.copy(user)
    view._real_role = user.role
    view.role = Role.COMMUNITY_MEMBER
    view.custom_role = None
    view._is_member_account_view = True

    real_save = type(user).save

    def save(*args, **kwargs):
        fields = kwargs.get("update_fields")
        if fields is None:
            fields = [f.name for f in view._meta.concrete_fields if not f.primary_key and f.name not in _PROTECTED]
        else:
            fields = [f for f in fields if f not in _PROTECTED]
        if not fields:
            return None
        kwargs["update_fields"] = fields
        return real_save(view, *args, **kwargs)

    view.save = save
    return view


def should_act_as_member(user) -> bool:
    """An executive (or Deceased Rep) with a member profile, currently on the community-member account."""
    return (
        getattr(user, "active_context", None) == DashboardContext.PERSONAL
        and not getattr(user, "is_superuser", False)
        and user.can_switch_dashboard_context()
    )
