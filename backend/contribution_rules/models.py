import uuid

from django.conf import settings
from django.db import models


class GeneralRateChangeLog(models.Model):
    """
    Audit trail for changes to the community-wide general contribution
    rates (what non-family members pay, by gender). This is the same kind
    of history FamilyAuditLog keeps for own-family rates — kept as its own
    small table here rather than bolted onto tenants.Community, since rate
    governance is squarely this module's job, not the tenant model's.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="general_rate_changes")
    old_male_amount = models.DecimalField(max_digits=10, decimal_places=2)
    old_female_amount = models.DecimalField(max_digits=10, decimal_places=2)
    new_male_amount = models.DecimalField(max_digits=10, decimal_places=2)
    new_female_amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=255, blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]


class MemberStatusRule(models.Model):
    """
    Whether members with a given Member.Status are exempt from mandatory
    contributions entirely — e.g. a Guest or an Inactive member is not
    obligated on any funeral's ledger. This is the "Member Status" factor
    the master brief lists alongside Family and Gender.

    If no row exists for a given community+status, DEFAULT_EXEMPT_STATUSES
    below is used, so a brand-new community works sensibly out of the box
    without an administrator having to configure this on day one.
    """

    DEFAULT_EXEMPT_STATUSES = {"inactive", "deceased"}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey("tenants.Community", on_delete=models.CASCADE, related_name="member_status_rules")
    status = models.CharField(max_length=20)
    is_exempt = models.BooleanField()
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["community", "status"], name="one_rule_per_status_per_community")
        ]


class DefaulterPolicy(models.Model):
    """
    Configurable thresholds for the automatic defaulter escalation described
    in the master brief: miss N contributions -> Warning; miss another ->
    High Warning; miss another -> Flagged (highlighted, Family Head and
    Treasurer notified, added to the Defaulters dashboard). One row per
    community; created lazily with sensible defaults (1 / 2 / 3) the first
    time it's read if it doesn't exist yet.
    """

    community = models.OneToOneField(
        "tenants.Community", on_delete=models.CASCADE, primary_key=True, related_name="defaulter_policy"
    )
    warning_threshold = models.PositiveIntegerField(default=1)
    high_warning_threshold = models.PositiveIntegerField(default=2)
    flag_threshold = models.PositiveIntegerField(default=3)
    updated_at = models.DateTimeField(auto_now=True)

    def tier_for(self, missed_count: int) -> str:
        if missed_count >= self.flag_threshold:
            return "flagged"
        if missed_count >= self.high_warning_threshold:
            return "high_warning"
        if missed_count >= self.warning_threshold:
            return "warning"
        return "none"
