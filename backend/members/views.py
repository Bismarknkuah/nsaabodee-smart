from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

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
            gender=self.request.query_params.get("gender"),
            sort_by=self.request.query_params.get("sort_by"),
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

    @action(detail=False, methods=["post"], url_path="bulk-upload")
    def bulk_upload(self, request):
        """
        'Executive should have access to upload data when necessary.'
        Uses the class-level permission_classes already applied to
        every other write action here (CanManageMembers,
        IsSameFamilyOrCommunityWide, etc.) — a Family Head or
        Secretary uploading a CSV gets exactly the same own-family-only
        restriction bulk_register_members enforces, the same
        restriction every other registration path on this platform
        already has.
        """
        import csv
        import io

        upload = request.FILES.get("file")
        if upload is None:
            return Response({"detail": "No file uploaded — attach a CSV file under the 'file' field."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            decoded = upload.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return Response({"detail": "Couldn't read the file as UTF-8 text — is it really a CSV?"}, status=status.HTTP_400_BAD_REQUEST)

        reader = csv.DictReader(io.StringIO(decoded))
        rows = [{(k or "").strip().lower(): v for k, v in row.items()} for row in reader]
        result = services.bulk_register_members(community=request.user.community, rows=rows, actor=request.user)
        return Response(result, status=status.HTTP_207_MULTI_STATUS if result["error_count"] else status.HTTP_201_CREATED)

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

    @action(detail=True, methods=["post"], url_path="transfer-to-town-elder", permission_classes=[IsAuthenticated, IsSameCommunity])
    def transfer_to_town_elder(self, request, id=None):
        """'Since you become a town elder the community admin or community executive should be able to transfer you to be part of the town elders ledger.'"""
        member = self.get_object()
        title = request.data.get("title", "")
        try:
            updated = services.transfer_to_town_elder(member=member, title=title, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(MemberSerializer(updated, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="remove-from-town-elder", permission_classes=[IsAuthenticated, IsSameCommunity])
    def remove_from_town_elder(self, request, id=None):
        """'The town leader should also have user management... to manage the town elders ledger' — includes taking someone off it."""
        member = self.get_object()
        try:
            updated = services.remove_from_town_elder(member=member, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(MemberSerializer(updated, context={"request": request}).data)

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated, IsSameCommunity])
    def wallet(self, request, id=None):
        """
        'If he doesn't get change, money balance should be credited to
        the member's wallet.' Anyone who can already view this member
        (the same scoping search_members already enforces) can see
        their wallet balance and history — a Collector genuinely needs
        this to know how much credit is available to apply toward a
        new obligation.
        """
        member = self.get_object()
        from .models import MemberWallet
        wallet = MemberWallet.objects.filter(member=member).first()
        return Response({
            "member_id": str(member.id),
            "balance": str(wallet.balance) if wallet else "0",
            "transactions": [
                {"id": str(t.id), "kind": t.kind, "amount": str(t.amount), "note": t.note, "created_at": t.created_at.isoformat()}
                for t in (wallet.transactions.all()[:20] if wallet else [])
            ],
        })


def _serialize_nomination(nomination):
    return {
        "id": str(nomination.id),
        "member_id": str(nomination.member_id),
        "member_name": nomination.member.full_name,
        "collector_type": nomination.collector_type,
        "scoped_family_name": nomination.scoped_family.name if nomination.scoped_family else None,
        "status": nomination.status,
        "nominated_by": nomination.nominated_by.username if nomination.nominated_by else None,
        "created_at": nomination.created_at.isoformat(),
        "approvals": [
            {"decided_by": a.decided_by.username, "decision": a.decision, "decided_at": a.decided_at.isoformat()}
            for a in nomination.approvals.all()
        ],
    }


class CollectorNominationsView(APIView):
    """
    'The collectors should be in 4 categories... for transparency, when
    one creates an account he needs other executives to approve it
    before that account can start collecting money.' GET -> every
    nomination for this actor's own community. POST {member_id,
    collector_type} -> a new pending nomination.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            nominations = services.list_collector_nominations(community=request.user.community, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response([_serialize_nomination(n) for n in nominations])

    def post(self, request):
        member_id = request.data.get("member_id")
        collector_type = request.data.get("collector_type", "")
        if not member_id:
            return Response({"detail": "'member_id' is required."}, status=status.HTTP_400_BAD_REQUEST)
        member = get_object_or_404(Member, id=member_id)
        try:
            nomination = services.nominate_collector(member=member, collector_type=collector_type, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(_serialize_nomination(nomination), status=status.HTTP_201_CREATED)


class DecideCollectorNominationView(APIView):
    """POST {decision: 'approve'|'reject'} -> this specific executive's own vote on one pending nomination."""
    permission_classes = [IsAuthenticated]

    def post(self, request, nomination_id):
        from .models import CollectorNomination

        nomination = get_object_or_404(CollectorNomination, id=nomination_id, community=request.user.community)
        decision = request.data.get("decision", "")
        try:
            updated = services.decide_collector_nomination(nomination=nomination, actor=request.user, decision=decision)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(_serialize_nomination(updated))
