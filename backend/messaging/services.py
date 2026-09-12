"""
Channel membership is computed, never stored — a person's access to a
channel is derived from their real role/community/family at the moment
they ask, the same "never a second source of truth to drift out of
sync" principle this platform already follows for permissions
elsewhere. Get-or-create is used throughout rather than requiring an
explicit provisioning step, so a channel simply exists the moment
anyone actually needs it.
"""
from django.core.exceptions import ValidationError

from .models import Channel, ChannelMessage


def get_or_create_platform_channel() -> Channel:
    channel, _ = Channel.objects.get_or_create(
        channel_type=Channel.ChannelType.PLATFORM, community=None, family=None,
        defaults={"name": "Platform Channel"},
    )
    return channel


def get_or_create_community_channel(community) -> Channel:
    channel, _ = Channel.objects.get_or_create(
        channel_type=Channel.ChannelType.COMMUNITY, community=community, family=None,
        defaults={"name": f"{community.name} Community Channel"},
    )
    return channel


def get_or_create_family_channel(family) -> Channel:
    channel, _ = Channel.objects.get_or_create(
        channel_type=Channel.ChannelType.FAMILY, community=family.community, family=family,
        defaults={"name": f"{family.name} Family Channel"},
    )
    return channel


def can_access_channel(*, user, channel: Channel) -> bool:
    """
    'A channel from top to down' — each channel's membership mirrors
    exactly one level of the real organizational hierarchy:
    """
    if user.is_superuser:
        return True

    if channel.channel_type == Channel.ChannelType.PLATFORM:
        # Platform Admin posts; every Community Admin, in every
        # community, can read and reply — the one channel that
        # deliberately crosses community boundaries, since it's how
        # the platform itself reaches every community's leadership.
        return user.role in ("platform_admin", "community_admin")

    if channel.channel_type == Channel.ChannelType.COMMUNITY:
        return user.community_id == channel.community_id

    if channel.channel_type == Channel.ChannelType.FAMILY:
        member = getattr(user, "member_profile", None)
        return bool(member and member.family_id == channel.family_id)

    return False


def list_my_channels(*, user) -> list:
    """Every channel this specific person actually belongs to — their community's, their family's if they're in one, and the platform channel if they're a Community Admin or Platform Admin."""
    channels = []
    if user.role in ("platform_admin",) or user.is_superuser:
        channels.append(get_or_create_platform_channel())
    if user.community_id:
        if user.role == "community_admin":
            channels.append(get_or_create_platform_channel())
        channels.append(get_or_create_community_channel(user.community))
        member = getattr(user, "member_profile", None)
        if member and member.family_id:
            channels.append(get_or_create_family_channel(member.family))
    # De-duplicate while preserving order (a Community Admin would
    # otherwise see the platform channel appended twice above).
    seen = set()
    unique = []
    for c in channels:
        if c.id not in seen:
            seen.add(c.id)
            unique.append(c)
    return unique


def post_message(*, channel: Channel, sender, content: str) -> ChannelMessage:
    if not can_access_channel(user=sender, channel=channel):
        raise ValidationError("You don't have access to this channel.")
    if not content.strip():
        raise ValidationError("A message can't be empty.")
    return ChannelMessage.objects.create(channel=channel, sender=sender, content=content.strip())


def list_messages(*, channel: Channel, actor) -> list:
    if not can_access_channel(user=actor, channel=channel):
        raise ValidationError("You don't have access to this channel.")
    return list(channel.messages.select_related("sender"))
