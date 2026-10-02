"""Welfare is created by the Community Welfare Manager only; older tests created it as the Admin or a Family Head. `wm_for(user)` gives the Welfare Manager of that user's community."""
from accounts.models import Role, User


def wm_for(user):
    community = user.community
    wm, _ = User.objects.get_or_create(username=f"welfare_manager_{community.slug}", defaults={"community": community, "role": Role.WELFARE_MANAGER})
    return wm
