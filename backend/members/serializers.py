from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from families.models import Family
from . import services
from .models import Member


class MemberFamilyMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Family
        fields = ["id", "name"]


class MemberSerializer(serializers.ModelSerializer):
    family_detail = MemberFamilyMiniSerializer(source="family", read_only=True)
    photo_url = serializers.SerializerMethodField()
    linked_username = serializers.CharField(source="linked_user.username", read_only=True, default=None)
    linked_role = serializers.CharField(source="linked_user.role", read_only=True, default=None)

    class Meta:
        model = Member
        fields = [
            "id", "membership_number", "full_name", "gender", "date_of_birth", "occupation",
            "phone", "address", "ghana_card_number", "photo_url", "family", "family_detail",
            "emergency_contact_name", "emergency_contact_phone", "status", "linked_username", "linked_role",
            "missed_contributions_count", "defaulter_tier", "defaulter_evaluated_at",
            "family_seniority", "is_town_leader",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "membership_number", "family_detail", "photo_url", "linked_username", "linked_role",
            "missed_contributions_count", "defaulter_tier", "defaulter_evaluated_at",
            "created_at", "updated_at",
        ]

    def get_photo_url(self, obj):
        request = self.context.get("request")
        if not obj.photo:
            return None
        return request.build_absolute_uri(obj.photo.url) if request else obj.photo.url


class MemberUpdateSerializer(serializers.Serializer):
    """
    The real fix for a genuine bug: MemberViewSet.partial_update used to
    pass raw `request.data` straight to services.update_member(**fields).
    That works fine for JSON requests, but a multipart-encoded PATCH (the
    DRF test client's own default when `format` isn't specified, and a
    real possibility from any browser form) represents each field as a
    QueryDict list — so `phone` arrived as `['0244000000']`, and
    Member.phone silently ended up storing the Python list's string
    representation instead of the actual value. Routing through a real
    serializer, the same pattern every other write in this app already
    uses, makes DRF's own field-level coercion respect this properly —
    there's no separate hand-rolled dict-copying path left to skip it.
    """
    full_name = serializers.CharField(max_length=255, required=False)
    gender = serializers.ChoiceField(choices=Member.Gender.choices, required=False)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    occupation = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    ghana_card_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    photo = serializers.ImageField(required=False, allow_null=True)
    emergency_contact_name = serializers.CharField(required=False, allow_blank=True)
    emergency_contact_phone = serializers.CharField(required=False, allow_blank=True)
    status = serializers.ChoiceField(choices=Member.Status.choices, required=False)
    family_seniority = serializers.ChoiceField(choices=Member.FamilySeniority.choices, required=False)
    is_town_leader = serializers.BooleanField(required=False)


class LinkMemberUserSerializer(serializers.Serializer):
    username = serializers.CharField()

    def save(self, **kwargs):
        request = self.context["request"]
        member = self.context["member"]
        User = get_user_model()
        try:
            user = User.objects.get(username=self.validated_data["username"], community=request.user.community)
        except User.DoesNotExist:
            raise serializers.ValidationError({"username": "No user with this username was found in this community."})
        try:
            return services.link_member_to_user(member=member, user=user, actor=request.user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))


class MemberRegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    gender = serializers.ChoiceField(choices=Member.Gender.choices)
    family_id = serializers.UUIDField(required=False, allow_null=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    occupation = serializers.CharField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(required=False, allow_blank=True, default="")
    address = serializers.CharField(required=False, allow_blank=True, default="")
    ghana_card_number = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    photo = serializers.ImageField(required=False, allow_null=True)
    emergency_contact_name = serializers.CharField(required=False, allow_blank=True, default="")
    emergency_contact_phone = serializers.CharField(required=False, allow_blank=True, default="")
    force_despite_duplicate = serializers.BooleanField(required=False, default=False)
    family_seniority = serializers.ChoiceField(choices=Member.FamilySeniority.choices, required=False)
    is_town_leader = serializers.BooleanField(required=False, default=False)

    def save(self, **kwargs):
        from .permissions import COMMUNITY_WIDE_MEMBER_ROLES

        request = self.context["request"]
        data = self.validated_data
        user = request.user

        family = None
        if data.get("family_id"):
            try:
                family = Family.objects.get(id=data["family_id"], community=request.user.community)
            except Family.DoesNotExist:
                raise serializers.ValidationError({"family_id": "Family not found in this community."})

        # A Family Head or Family Secretary registers members into their
        # OWN family only — neither gets the community-wide reach a
        # Chairman/Secretary(-of-the-community)/Admin has. If they don't
        # specify a family at all, default it to their own rather than
        # erroring, since "which family" is never actually ambiguous
        # for either of them.
        if not user.is_superuser and user.role not in COMMUNITY_WIDE_MEMBER_ROLES:
            own_member = getattr(user, "member_profile", None)
            own_family = own_member.family if (own_member and own_member.family_id) else None
            if own_family is None:
                raise serializers.ValidationError(
                    "You're not registered as part of a family yet, so you can't register members yourself."
                )
            if family is not None and family.id != own_family.id:
                raise serializers.ValidationError({"family_id": "You can only register members into your own family."})
            family = own_family

        # "Town leader" is a communal designation (the chief and his
        # elders) — not something a single family's own head or
        # secretary should be able to grant, even for a member of their
        # own family. Family-scoped roles can register/edit within their
        # own family freely, but this one flag stays a platform/
        # community-level call.
        if data.get("is_town_leader") and not (user.is_superuser or user.role in COMMUNITY_WIDE_MEMBER_ROLES):
            raise serializers.ValidationError({"is_town_leader": "Only a community-wide administrator can designate someone a town leader."})

        try:
            member = services.register_member(
                community=request.user.community,
                full_name=data["full_name"],
                gender=data["gender"],
                family=family,
                date_of_birth=data.get("date_of_birth"),
                occupation=data.get("occupation", ""),
                phone=data.get("phone", ""),
                address=data.get("address", ""),
                ghana_card_number=data.get("ghana_card_number") or None,
                photo=data.get("photo"),
                emergency_contact_name=data.get("emergency_contact_name", ""),
                emergency_contact_phone=data.get("emergency_contact_phone", ""),
                registered_by=request.user,
                force_despite_duplicate=data.get("force_despite_duplicate", False),
                family_seniority=data.get("family_seniority"),
                is_town_leader=data.get("is_town_leader", False),
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages)

        possible_duplicates = services.find_possible_duplicates(
            community=request.user.community, full_name=data["full_name"], phone=data.get("phone", "")
        )
        possible_duplicates = [m for m in possible_duplicates if m.id != member.id]
        return member, possible_duplicates


class AssignRoleSerializer(serializers.Serializer):
    """'Specific roles to select when the community admin wants to assign a role... should have more options as he supervises and manages the community system.'"""
    role = serializers.ChoiceField(choices=services.ASSIGNABLE_COMMUNITY_ROLES)
    username = serializers.CharField(required=False, allow_blank=True, default="")
    password = serializers.CharField(required=False, allow_blank=True, default="", write_only=True)

    def save(self, **kwargs):
        member = self.context["member"]
        actor = self.context["request"].user
        data = self.validated_data
        try:
            return services.assign_role_to_member(
                member=member, role=data["role"], actor=actor,
                username=data.get("username") or None, password=data.get("password") or None,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages if hasattr(exc, "messages") else str(exc))
