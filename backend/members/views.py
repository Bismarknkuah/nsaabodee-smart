from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated

from accounts.permissions import RequiresExecutiveContext, RequiresExecutiveContextForWrites
from rest_framework.response import Response

from . import services
from .models import Member
from .permissions import CanManageMembers, IsSameCommunity, IsSameFamilyOrCommunityWide
from .serializers import AssignRoleSerializer, LinkMemberUserSerializer, MemberRegisterSerializer, MemberSerializer, MemberUpdateSerializer


class MemberViewSet(viewsets.ModelViewSet):
    """
    /api/members/                    GET list (?search=&family=&status=&defaulter_tier=)
    /api/members/                    POST register (collector+, auto-enrolls into open funerals)
    /api/members/{id}/               GET / PATCH
    /api/members/{id}/card/          GET the digital membership card (photo + QR)
    /api/members/defaulters/         GET the Defaulters Dashboard for the whole community
    """

    serializer_class = MemberSerializer
    permission_classes = [IsAuthenticated, CanManageMembers, IsSameCommunity, IsSameFamilyOrCommunityWide, RequiresExecutiveContextForWrites]
    lookup_field = "id"
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "request": self.request}

    def get_queryset(self):
        user = self.request.user
        qs = services.search_members(
            community=user.community if not user.is_superuser else None,
            query=self.request.query_params.get("search", ""),
            family_id=self.request.query_params.get("family"),
            status=self.request.query_params.get("status"),
            defaulter_tier=self.request.query_params.get("defaulter_tier"),
            actor=user,
        )
        return qs

    def create(self, request, *args, **kwargs):
        serializer = MemberRegisterSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        member, possible_duplicates = serializer.save()
        response = MemberSerializer(member, context={"request": request}).data
        if possible_duplicates:
            response["possible_duplicates"] = MemberSerializer(
                possible_duplicates, many=True, context={"request": request}
            ).data
        return Response(response, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        member = self.get_object()
        serializer = MemberUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        from .permissions import COMMUNITY_WIDE_MEMBER_ROLES
        if "is_town_leader" in serializer.validated_data and not (
            request.user.is_superuser or request.user.role in COMMUNITY_WIDE_MEMBER_ROLES
        ):
            return Response(
                {"detail": ["Only a community-wide administrator can change town-leader status."]},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            services.update_member(member=member, actor=request.user, **serializer.validated_data)
        except DjangoValidationError as exc:
            # message_dict (field -> [messages]) when the error came from
            # full_clean() on multiple fields; falls back to the flat
            # message list for a single non-field error. Using .messages
            # unconditionally here previously flattened field-specific
            # errors into an unhelpful, unattributed message list — e.g.
            # "This field cannot be blank" with no indication of WHICH
            # field, which made a real bug (see Member.registered_by)
            # far harder to diagnose than it needed to be.
            detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            return Response({"detail": detail}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MemberSerializer(member, context={"request": request}).data)

    @action(detail=True, methods=["get"])
    def card(self, request, id=None):
        member = self.get_object()
        return Response(services.digital_membership_card(member))

    @action(detail=False, methods=["get"])
    def defaulters(self, request):
        qs = self.get_queryset().exclude(defaulter_tier=Member.DefaulterTier.NONE).order_by("-missed_contributions_count")
        from nsaabodeeq.pagination import paginate_response
        return paginate_response(request, qs, MemberSerializer, serializer_context={"request": request})

    @action(detail=True, methods=["post"], url_path="link-user")
    def link_user(self, request, id=None):
        member = self.get_object()
        serializer = LinkMemberUserSerializer(data=request.data, context={"request": request, "member": member})
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(MemberSerializer(updated, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="assign-role", permission_classes=[IsAuthenticated, CanManageMembers, IsSameCommunity, IsSameFamilyOrCommunityWide, RequiresExecutiveContext])
    def assign_role(self, request, id=None):
        """'Specific roles to select when the community admin wants to assign a role... more options as he supervises and manages the community system.'"""
        member = self.get_object()
        serializer = AssignRoleSerializer(data=request.data, context={"request": request, "member": member})
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response({"member_id": str(member.id), "role": user.role, "username": user.username})

    @action(detail=True, methods=["post"], url_path="revoke-role", permission_classes=[IsAuthenticated, CanManageMembers, IsSameCommunity, IsSameFamilyOrCommunityWide, RequiresExecutiveContext])
    def revoke_role(self, request, id=None):
        """'Assign and revoke roles and permissions.'"""
        member = self.get_object()
        try:
            user = services.revoke_role_from_member(member=member, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"member_id": str(member.id), "role": user.role, "username": user.username})
