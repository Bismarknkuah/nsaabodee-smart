from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed


class CommunityAwareJWTAuthentication(JWTAuthentication):
    """
    Same JWT authentication DRF already used everywhere, plus one real
    check: if this user's community was given a temporary/rental access
    period (see tenants.models.Community.access_expires_at) and that
    period has passed, the request is rejected here — regardless of how
    long the access token itself still has left to live. Without this,
    someone whose community's paid access just ran out could keep
    working right up until their token's own unrelated expiry, which
    defeats the entire point of a real, enforced rental period.

    A user with no community at all (Super Admin / Platform Admin) is
    never affected — this only ever blocks a request tied to a specific
    community whose OWN access has actually expired.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if user.community_id and user.community and user.community.is_access_expired:
            raise AuthenticationFailed(
                "This community's access period has ended. Contact your platform administrator to renew it.",
                code="community_access_expired",
            )
        return user
