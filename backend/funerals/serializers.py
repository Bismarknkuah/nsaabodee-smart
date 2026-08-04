from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from families.models import Family
from members.models import Member
from . import services
from .models import ContributionObligation, ContributionPayment, FuneralCommitteePosition, FuneralDeskAssignment, FuneralEvent, MemorialTribute, PaymentReversal


class FuneralEventSerializer(serializers.ModelSerializer):
    deceased_family_name = serializers.CharField(source="deceased_family.name", read_only=True)

    class Meta:
        model = FuneralEvent
        fields = [
            "id", "deceased_name", "deceased_gender", "deceased_family", "deceased_family_name",
            "date_of_death", "deceased_date_of_birth", "burial_date", "funeral_date",
            "collection_start_date", "collection_end_date", "status",
            "own_family_amount", "general_male_amount", "general_female_amount",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "status", "own_family_amount", "general_male_amount",
                            "general_female_amount", "created_at", "updated_at"]


class FuneralEventCreateSerializer(serializers.Serializer):
    deceased_name = serializers.CharField(max_length=255)
    deceased_gender = serializers.ChoiceField(choices=FuneralEvent.Gender.choices)
    deceased_family_id = serializers.UUIDField()
    date_of_death = serializers.DateField()
    deceased_date_of_birth = serializers.DateField(required=False, allow_null=True)
    burial_date = serializers.DateField(required=False, allow_null=True)
    funeral_date = serializers.DateField(required=False, allow_null=True)
    collection_start_date = serializers.DateField()
    collection_end_date = serializers.DateField(required=False, allow_null=True)
    # Optional one-off overrides. If omitted, the family's standing rate and
    # the community's default general rates are used automatically.
    own_family_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    general_male_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    general_female_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)

    def save(self, **kwargs):
        request = self.context["request"]
        data = self.validated_data
        try:
            deceased_family = Family.objects.get(id=data["deceased_family_id"], community=request.user.community)
        except Family.DoesNotExist:
            raise serializers.ValidationError({"deceased_family_id": "Family not found in this community."})

        try:
            return services.create_funeral_event(
                community=request.user.community,
                deceased_name=data["deceased_name"],
                deceased_gender=data["deceased_gender"],
                deceased_family=deceased_family,
                date_of_death=data["date_of_death"],
                deceased_date_of_birth=data.get("deceased_date_of_birth"),
                burial_date=data.get("burial_date"),
                funeral_date=data.get("funeral_date"),
                collection_start_date=data["collection_start_date"],
                collection_end_date=data.get("collection_end_date"),
                own_family_amount=data.get("own_family_amount"),
                general_male_amount=data.get("general_male_amount"),
                general_female_amount=data.get("general_female_amount"),
                actor=request.user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class RequestFuneralEventSerializer(serializers.Serializer):
    """
    'Is the family head who will open the ledger when there's a
    funeral.' Same shape as FuneralEventCreateSerializer, but creates a
    PENDING_APPROVAL funeral instead of an immediately-active one, and a
    Family Head is only allowed to request one for his OWN family — the
    same scoping already used for member registration and task
    assignment. Community-wide roles keep the ability to request on
    behalf of any family too (e.g. no family head assigned yet).
    """
    deceased_name = serializers.CharField(max_length=255)
    deceased_gender = serializers.ChoiceField(choices=FuneralEvent.Gender.choices)
    deceased_family_id = serializers.UUIDField(required=False, allow_null=True)
    date_of_death = serializers.DateField()
    deceased_date_of_birth = serializers.DateField(required=False, allow_null=True)
    burial_date = serializers.DateField(required=False, allow_null=True)
    funeral_date = serializers.DateField(required=False, allow_null=True)
    collection_start_date = serializers.DateField()
    collection_end_date = serializers.DateField(required=False, allow_null=True)
    own_family_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    general_male_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    general_female_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)

    def save(self, **kwargs):
        request = self.context["request"]
        user = request.user
        data = self.validated_data

        deceased_family = None
        if data.get("deceased_family_id"):
            try:
                deceased_family = Family.objects.get(id=data["deceased_family_id"], community=user.community)
            except Family.DoesNotExist:
                raise serializers.ValidationError({"deceased_family_id": "Family not found in this community."})

        if not user.is_superuser and not user.can_manage_families():
            own_member = getattr(user, "member_profile", None)
            own_family = own_member.family if (own_member and own_member.family_id) else None
            if own_family is None:
                raise serializers.ValidationError(
                    "You're not registered as part of a family, so you can't request a funeral opening."
                )
            if deceased_family is not None and deceased_family.id != own_family.id:
                raise serializers.ValidationError({"deceased_family_id": "You can only request a funeral opening for your own family."})
            deceased_family = own_family

        if deceased_family is None:
            raise serializers.ValidationError({"deceased_family_id": "This field is required."})

        try:
            return services.request_funeral_event(
                community=user.community,
                deceased_name=data["deceased_name"],
                deceased_gender=data["deceased_gender"],
                deceased_family=deceased_family,
                date_of_death=data["date_of_death"],
                deceased_date_of_birth=data.get("deceased_date_of_birth"),
                burial_date=data.get("burial_date"),
                funeral_date=data.get("funeral_date"),
                collection_start_date=data["collection_start_date"],
                collection_end_date=data.get("collection_end_date"),
                own_family_amount=data.get("own_family_amount"),
                general_male_amount=data.get("general_male_amount"),
                general_female_amount=data.get("general_female_amount"),
                actor=user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class ObligationMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ["id", "full_name", "gender", "family"]


class ContributionObligationSerializer(serializers.ModelSerializer):
    member = ObligationMemberSerializer(read_only=True)
    balance = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    payment_status = serializers.CharField(read_only=True)

    class Meta:
        model = ContributionObligation
        fields = [
            "id", "funeral_event", "member", "rate_type",
            "expected_amount", "amount_paid", "balance", "payment_status",
        ]


class RecordPaymentSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    method = serializers.ChoiceField(choices=ContributionPayment.Method.choices)
    client_op_id = serializers.UUIDField(required=False, allow_null=True)

    def save(self, **kwargs):
        request = self.context["request"]
        obligation = self.context["obligation"]
        try:
            return services.record_payment(
                obligation=obligation,
                amount=self.validated_data["amount"],
                method=self.validated_data["method"],
                collector=request.user,
                client_op_id=self.validated_data.get("client_op_id"),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class ContributionPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContributionPayment
        fields = ["id", "obligation", "amount", "method", "receipt_number", "collected_by", "paid_at"]


class MemberRateOverrideSerializer(serializers.Serializer):
    member = serializers.UUIDField(source="member_id")
    member_name = serializers.CharField(source="member.full_name", read_only=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)


class SetMemberRateOverridesSerializer(serializers.Serializer):
    """{overrides: {member_id: amount, ...}} — 'set an amount for each member [of their own family] have to pay.'"""
    overrides = serializers.DictField(child=serializers.DecimalField(max_digits=10, decimal_places=2))

    def save(self, **kwargs):
        request = self.context["request"]
        funeral = self.context["funeral"]
        try:
            services.set_member_rate_overrides(
                funeral=funeral, overrides=self.validated_data["overrides"], actor=request.user,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)
        return services.list_member_rate_overrides(funeral)


class DeskAssignmentSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    assigned_by_username = serializers.CharField(source="assigned_by.username", read_only=True, default=None)
    approved_by_username = serializers.CharField(source="approved_by.username", read_only=True, default=None)
    deceased_name = serializers.CharField(source="funeral_event.deceased_name", read_only=True)

    class Meta:
        model = FuneralDeskAssignment
        fields = [
            "id", "funeral_event", "deceased_name", "user", "username", "desk_type",
            "assigned_by_username", "is_active", "approved_by_username", "approved_at", "created_at",
        ]
        read_only_fields = fields


class AssignDeskWorkerSerializer(serializers.Serializer):
    """Either `user_id` (an existing account) or `new_username`+`new_password` (creates one on the spot) — see services.assign_desk_worker."""
    user_id = serializers.UUIDField(required=False, allow_null=True)
    new_username = serializers.CharField(required=False, allow_blank=True, default="")
    new_password = serializers.CharField(required=False, allow_blank=True, default="", write_only=True)
    new_email = serializers.EmailField(required=False, allow_blank=True, default="")
    desk_type = serializers.ChoiceField(choices=FuneralDeskAssignment.DeskType.choices)

    def save(self, **kwargs):
        request = self.context["request"]
        funeral = self.context["funeral"]
        data = self.validated_data

        user = None
        if data.get("user_id"):
            from accounts.models import User
            try:
                user = User.objects.get(id=data["user_id"], community=funeral.community)
            except User.DoesNotExist:
                raise serializers.ValidationError({"user_id": "User not found in this community."})

        try:
            return services.assign_desk_worker(
                funeral=funeral, actor=request.user, desk_type=data["desk_type"], user=user,
                new_username=data.get("new_username") or None, new_password=data.get("new_password") or None,
                new_email=data.get("new_email", ""),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class FuneralCommitteePositionSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)
    deceased_name = serializers.CharField(source="funeral_event.deceased_name", read_only=True)
    appointed_by_username = serializers.CharField(source="appointed_by.username", read_only=True, default=None)

    class Meta:
        model = FuneralCommitteePosition
        fields = ["id", "funeral_event", "deceased_name", "member", "member_name", "title", "appointed_by_username", "appointed_at"]
        read_only_fields = ["id", "funeral_event", "deceased_name", "member_name", "appointed_by_username", "appointed_at"]


class AppointCommitteePositionSerializer(serializers.Serializer):
    """'Every funeral creates a committee workspace... Custom positions allowed.'"""
    member_id = serializers.UUIDField()
    title = serializers.CharField(max_length=100)

    def save(self, **kwargs):
        request = self.context["request"]
        funeral = self.context["funeral"]
        try:
            member = Member.objects.get(id=self.validated_data["member_id"], community=funeral.community)
        except Member.DoesNotExist:
            raise serializers.ValidationError({"member_id": "Member not found in this community."})
        try:
            return services.appoint_committee_position(funeral=funeral, member=member, title=self.validated_data["title"], actor=request.user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class ManageMemorialPageSerializer(serializers.Serializer):
    """Family/admin-only write — create or update the funeral's memorial page."""
    tribute_message = serializers.CharField(required=False, allow_blank=True)
    photo = serializers.ImageField(required=False, allow_null=True)
    show_contribution_total = serializers.BooleanField(required=False)
    is_published = serializers.BooleanField(required=False)

    def save(self, **kwargs):
        request = self.context["request"]
        funeral = self.context["funeral"]
        data = self.validated_data
        try:
            return services.create_or_update_memorial_page(
                funeral=funeral, actor=request.user,
                tribute_message=data.get("tribute_message"), photo=data.get("photo"),
                show_contribution_total=data.get("show_contribution_total"), is_published=data.get("is_published"),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class SubmitTributeSerializer(serializers.Serializer):
    """Public — no login required. Always lands unapproved; never visible anywhere until the family or an admin approves it."""
    author_name = serializers.CharField(max_length=255)
    message = serializers.CharField()

    def save(self, **kwargs):
        funeral = self.context["funeral"]
        try:
            return services.submit_tribute(funeral=funeral, author_name=self.validated_data["author_name"], message=self.validated_data["message"])
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)


class TributeManagementSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemorialTribute
        fields = ["id", "author_name", "message", "is_approved", "created_at"]
        read_only_fields = fields


class PaymentReversalSerializer(serializers.ModelSerializer):
    payment_receipt_number = serializers.CharField(source="payment.receipt_number", read_only=True)
    payment_amount = serializers.DecimalField(source="payment.amount", max_digits=10, decimal_places=2, read_only=True)
    requested_by_username = serializers.CharField(source="requested_by.username", read_only=True)
    decided_by_username = serializers.CharField(source="decided_by.username", read_only=True, default=None)

    class Meta:
        model = PaymentReversal
        fields = [
            "id", "payment", "payment_receipt_number", "payment_amount", "reason", "status",
            "requested_by", "requested_by_username", "requested_at",
            "decided_by", "decided_by_username", "decided_at", "decision_notes",
        ]
        read_only_fields = fields


class RequestPaymentReversalSerializer(serializers.Serializer):
    """'Every reversal must be logged with the reason...' — the reason is required, not optional, since it becomes part of the permanent audit trail."""
    reason = serializers.CharField()

    def save(self, **kwargs):
        payment = self.context["payment"]
        actor = self.context["request"].user
        try:
            return services.request_payment_reversal(payment=payment, reason=self.validated_data["reason"], actor=actor)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class DecidePaymentReversalSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def save(self, **kwargs):
        reversal = self.context["reversal"]
        actor = self.context["request"].user
        approve = self.context["approve"]
        try:
            if approve:
                return services.approve_payment_reversal(reversal=reversal, actor=actor, notes=self.validated_data.get("notes", ""))
            return services.reject_payment_reversal(reversal=reversal, actor=actor, notes=self.validated_data.get("notes", ""))
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))
