from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import RequiresExecutiveContext
from . import services
from .models import ContributionObligation, ContributionPayment, FuneralEvent
from .permissions import (
    CanApproveFuneralOpening,
    CanManageFunerals,
    CanRecordPayments,
    CanRecordPaymentsOrIsDeskWorker,
    CanRequestFuneralOpening,
    IsSameCommunity,
    is_desk_worker_for,
)
from .serializers import (
    AppointCommitteePositionSerializer,
    AssignDeskWorkerSerializer,
    ContributionObligationSerializer,
    ContributionPaymentSerializer,
    DecidePaymentReversalSerializer,
    DeskAssignmentSerializer,
    FuneralCommitteePositionSerializer,
    FuneralEventCreateSerializer,
    FuneralEventSerializer,
    ManageMemorialPageSerializer,
    MemberRateOverrideSerializer,
    PaymentReversalSerializer,
    RecordPaymentSerializer,
    RequestFuneralEventSerializer,
    RequestPaymentReversalSerializer,
    SetMemberRateOverridesSerializer,
    SubmitTributeSerializer,
    TributeManagementSerializer,
)


class FuneralEventViewSet(viewsets.ModelViewSet):
    """
    /api/funerals/                          GET list (?status=active to see all concurrently-open funerals)
    /api/funerals/                          POST create (Community Admin+, immediately active, auto-generates the ledger)
    /api/funerals/request/                  POST request an opening (Family Head, own family only, OR Community Admin+) — starts PENDING_APPROVAL, bills nobody yet
    /api/funerals/{id}/approve-opening/     POST (Secretary/Chairman/Admin) — the 2nd distinct approval activates the funeral and bills everyone
    /api/funerals/{id}/reject-opening/      POST (Secretary/Chairman/Admin) — cancels a still-pending request
    /api/funerals/{id}/approval-progress/   GET how many of the required 2 approvals are in, and who's given them
    /api/funerals/{id}/                     GET retrieve
    /api/funerals/{id}/close/               POST close
    /api/funerals/{id}/summary/             GET own-family vs general breakdown
    /api/funerals/{id}/obligations/         GET ledger, filterable by ?rate_type= & ?payment_status=
    /api/funerals/{id}/obligations/{oid}/record-payment/  POST
    """

    serializer_class = FuneralEventSerializer
    permission_classes = [IsAuthenticated, CanManageFunerals, IsSameCommunity]
    lookup_field = "id"
    http_method_names = ["get", "post", "delete", "head", "options"]  # delete is only ever used for the desk-assignments sub-resource — see destroy() below

    def destroy(self, request, *args, **kwargs):
        """
        'delete' had to be added to http_method_names above so the
        desk-assignments sub-resource (DELETE .../desk-assignments/{id}/)
        works — DRF's router wires that up as a genuinely separate
        route from this one, but ModelViewSet still auto-generates a
        DELETE handler for the funeral ITSELF too unless explicitly
        blocked here. Funerals are closed, never deleted — this override
        keeps that true regardless of what else needed "delete" enabling.
        """
        return Response(
            {"detail": "Funerals are never deleted — close them instead (POST .../close/)."},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def get_queryset(self):
        user = self.request.user
        qs = FuneralEvent.objects.select_related("deceased_family", "community")
        if not user.is_superuser:
            qs = qs.filter(community=user.community)
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = FuneralEventCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        funeral = serializer.save()
        return Response(FuneralEventSerializer(funeral).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated, CanApproveFuneralOpening, RequiresExecutiveContext, IsSameCommunity])
    def close(self, request, id=None):
        """
        'The community chairman or secretary decides the time to close
        the ledger.' Reuses the exact same role tier that can approve a
        funeral's OPENING (Secretary/Chairman/Community Admin+) — the
        same people trusted to let billing start are trusted to decide
        when collecting stops.
        """
        funeral = self.get_object()
        try:
            services.close_funeral_event(funeral=funeral, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        return Response(FuneralEventSerializer(funeral).data)

    @action(detail=False, methods=["post"], url_path="request", permission_classes=[IsAuthenticated, CanRequestFuneralOpening])
    def request_opening(self, request):
        """POST -> a PENDING_APPROVAL funeral, no obligations generated yet. See RequestFuneralEventSerializer for the family-head scoping."""
        serializer = RequestFuneralEventSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        funeral = serializer.save()
        return Response(FuneralEventSerializer(funeral).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="approve-opening", permission_classes=[IsAuthenticated, CanApproveFuneralOpening, RequiresExecutiveContext, IsSameCommunity])
    def approve_opening(self, request, id=None):
        funeral = self.get_object()
        try:
            updated = services.approve_funeral_opening(funeral=funeral, approver=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            **FuneralEventSerializer(updated).data,
            "approval_progress": services.funeral_approval_progress(updated),
        })

    @action(detail=True, methods=["post"], url_path="reject-opening", permission_classes=[IsAuthenticated, CanApproveFuneralOpening, RequiresExecutiveContext, IsSameCommunity])
    def reject_opening(self, request, id=None):
        funeral = self.get_object()
        try:
            updated = services.reject_funeral_opening(funeral=funeral, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        return Response(FuneralEventSerializer(updated).data)

    @action(detail=True, methods=["get"], url_path="approval-progress")
    def approval_progress(self, request, id=None):
        funeral = self.get_object()
        return Response(services.funeral_approval_progress(funeral))

    @action(detail=True, methods=["get", "post"], url_path="member-rate-overrides", permission_classes=[IsAuthenticated, IsSameCommunity])
    def member_rate_overrides(self, request, id=None):
        """
        GET -> current per-member overrides for this funeral. POST
        {overrides: {member_id: amount}} -> set/update them. Only the
        deceased family's own Head or Secretary, or Community Admin+ —
        the same "your own family only" scoping used for member
        registration and task assignment.
        """
        funeral = self.get_object()
        if request.method == "GET":
            return Response(MemberRateOverrideSerializer(services.list_member_rate_overrides(funeral), many=True).data)

        user = request.user
        if not (user.is_superuser or user.can_manage_families()):
            own_member = getattr(user, "member_profile", None)
            own_family_id = own_member.family_id if own_member else None
            is_this_familys_officer = (
                own_family_id == funeral.deceased_family_id
                and user.role in ("family_head", "family_secretary")
            )
            if not is_this_familys_officer:
                return Response(
                    {"detail": "Only this family's own head or secretary can set custom amounts for its members."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = SetMemberRateOverridesSerializer(data=request.data, context={"request": request, "funeral": funeral})
        serializer.is_valid(raise_exception=True)
        overrides = serializer.save()
        return Response(MemberRateOverrideSerializer(overrides, many=True).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"], url_path="desk-assignments", permission_classes=[IsAuthenticated, IsSameCommunity])
    def desk_assignments(self, request, id=None):
        """
        GET -> everyone currently assigned to this funeral's desk(s).
        POST -> assign someone new — "head of the family should be able
        to add one or more users... some who could be a member or not."
        Permission is checked inside services.assign_desk_worker itself
        (own family's Head/Secretary, or community Chairman/Secretary/
        Admin) so the same rule is enforced whether this is called
        directly or from anywhere else that might reuse the service.
        """
        funeral = self.get_object()
        if request.method == "GET":
            return Response(DeskAssignmentSerializer(services.list_desk_assignments(funeral), many=True).data)

        serializer = AssignDeskWorkerSerializer(data=request.data, context={"request": request, "funeral": funeral})
        serializer.is_valid(raise_exception=True)
        assignment = serializer.save()
        return Response(DeskAssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"desk-assignments/(?P<assignment_id>[^/.]+)", permission_classes=[IsAuthenticated, IsSameCommunity])
    def remove_desk_assignment(self, request, id=None, assignment_id=None):
        from .models import FuneralDeskAssignment
        funeral = self.get_object()
        assignment = get_object_or_404(FuneralDeskAssignment, id=assignment_id, funeral_event=funeral)
        try:
            services.remove_desk_worker(funeral=funeral, user=assignment.user, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get", "post"], url_path="committee-positions", permission_classes=[IsAuthenticated, IsSameCommunity])
    def committee_positions(self, request, id=None):
        """
        GET -> the whole committee, visible community-wide, same as
        desk assignments. POST -> appoint someone — community-wide
        leadership, or the deceased's own family Head/Secretary, per
        services._can_organize_committee_for.
        """
        funeral = self.get_object()
        if request.method == "GET":
            return Response(FuneralCommitteePositionSerializer(services.list_committee_positions(funeral=funeral), many=True).data)

        serializer = AppointCommitteePositionSerializer(data=request.data, context={"request": request, "funeral": funeral})
        serializer.is_valid(raise_exception=True)
        position = serializer.save()
        return Response(FuneralCommitteePositionSerializer(position).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"committee-positions/(?P<position_id>[^/.]+)", permission_classes=[IsAuthenticated, IsSameCommunity])
    def remove_committee_position(self, request, id=None, position_id=None):
        from .models import FuneralCommitteePosition
        funeral = self.get_object()
        position = get_object_or_404(FuneralCommitteePosition, id=position_id, funeral_event=funeral)
        try:
            services.remove_committee_position(position=position, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="my-committee-positions", permission_classes=[IsAuthenticated])
    def my_committee_positions(self, request):
        """'Each role receives only relevant dashboard' — the honest, lightest-weight version: a member's own committee assignments, across every funeral, in one place."""
        member = getattr(request.user, "member_profile", None)
        return Response(FuneralCommitteePositionSerializer(services.list_my_committee_positions(member=member), many=True).data)

    @action(detail=True, methods=["get"], url_path="qr-code", permission_classes=[IsAuthenticated, IsSameCommunity])
    def qr_code(self, request, id=None):
        """'The community admin should be able to generate a barcode so that it can be printed and pasted for guests to use to donate their gift or contribute.'"""
        funeral = self.get_object()
        return Response({"qr_code_base64": services.generate_funeral_qr_code_base64(funeral), "url": funeral.qr_payload})

    @action(detail=True, methods=["get"], url_path="memorial", permission_classes=[AllowAny])
    def memorial_public(self, request, id=None):
        """
        The one genuinely public read in this whole platform — no login,
        no community check. Deliberately bypasses self.get_object() (its
        community-scoping assumes an authenticated user with a community
        of their own, which an anonymous visitor never has) and looks
        the funeral up directly instead.
        """
        funeral = get_object_or_404(FuneralEvent, id=id)
        data = services.get_public_memorial_page(funeral)
        if data is None:
            return Response({"detail": "This funeral doesn't have a published memorial page."}, status=status.HTTP_404_NOT_FOUND)
        return Response(data)

    @action(detail=True, methods=["post"], url_path="memorial/manage", permission_classes=[IsAuthenticated, IsSameCommunity])
    def memorial_manage(self, request, id=None):
        """Family officer or Community Admin+ only — create/update this funeral's memorial page."""
        funeral = self.get_object()
        serializer = ManageMemorialPageSerializer(data=request.data, context={"request": request, "funeral": funeral})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(services.get_public_memorial_page(funeral) or {"detail": "Saved, but not currently published."})

    @action(detail=True, methods=["post"], url_path="memorial/tributes", permission_classes=[AllowAny])
    def submit_tribute(self, request, id=None):
        """Public — anyone can leave a tribute, no login required. Always lands unapproved."""
        funeral = get_object_or_404(FuneralEvent, id=id)
        serializer = SubmitTributeSerializer(data=request.data, context={"funeral": funeral})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Thank you — your tribute will appear once it's been reviewed."}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="memorial/tributes/manage", permission_classes=[IsAuthenticated, IsSameCommunity])
    def manage_tributes(self, request, id=None):
        """Family officer or Community Admin+ only — every tribute, pending included, so there's something to actually moderate."""
        funeral = self.get_object()
        try:
            tributes = services.list_all_tributes_for_management(funeral=funeral, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_403_FORBIDDEN)
        return Response(TributeManagementSerializer(tributes, many=True).data)

    @action(detail=True, methods=["post"], url_path=r"memorial/tributes/(?P<tribute_id>[^/.]+)/approve", permission_classes=[IsAuthenticated, IsSameCommunity])
    def approve_tribute(self, request, id=None, tribute_id=None):
        from .models import MemorialTribute
        funeral = self.get_object()
        tribute = get_object_or_404(MemorialTribute, id=tribute_id, memorial_page__funeral_event=funeral)
        try:
            services.approve_tribute(tribute=tribute, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_403_FORBIDDEN)
        return Response(TributeManagementSerializer(tribute).data)

    @action(detail=True, methods=["delete"], url_path=r"memorial/tributes/(?P<tribute_id>[^/.]+)", permission_classes=[IsAuthenticated, IsSameCommunity])
    def remove_tribute(self, request, id=None, tribute_id=None):
        from .models import MemorialTribute
        funeral = self.get_object()
        tribute = get_object_or_404(MemorialTribute, id=tribute_id, memorial_page__funeral_event=funeral)
        try:
            services.reject_tribute(tribute=tribute, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_403_FORBIDDEN)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def summary(self, request, id=None):
        funeral = self.get_object()
        return Response(services.funeral_summary(funeral))

    @action(detail=True, methods=["get"])
    def obligations(self, request, id=None):
        funeral = self.get_object()
        qs = funeral.obligations.select_related("member", "member__family")
        rate_type = request.query_params.get("rate_type")
        if rate_type:
            qs = qs.filter(rate_type=rate_type)
        payment_status = request.query_params.get("payment_status")
        if payment_status == "unpaid":
            qs = qs.filter(amount_paid=0)
        elif payment_status in ("paid", "partial"):
            # payment_status is a computed property, not a DB column, so
            # it can't be filtered in the queryset itself — but it CAN
            # still be paginated after filtering in Python, same as any
            # other list here.
            qs = [o for o in qs if o.payment_status == payment_status]
        from nsaabodeeq.pagination import paginate_response
        return paginate_response(request, qs, ContributionObligationSerializer)

    @action(
        detail=True, methods=["post"], url_path=r"obligations/(?P<obligation_id>[^/.]+)/record-payment",
        permission_classes=[IsAuthenticated, CanRecordPaymentsOrIsDeskWorker, RequiresExecutiveContext, IsSameCommunity],
    )
    def record_payment(self, request, id=None, obligation_id=None):
        funeral = self.get_object()
        user = request.user
        obligation = get_object_or_404(ContributionObligation, id=obligation_id, funeral_event=funeral)

        from .permissions import PAYMENT_COLLECTING_ROLES
        own_member = getattr(user, "member_profile", None)
        # "Unless they are paying for themselves" — every role is ALSO
        # a community member with their own obligations; this is
        # checked against the actual obligation being recorded, not a
        # blanket role grant, so it can never be used to record
        # someone ELSE's payment under the guise of "self-payment."
        is_own_obligation = bool(own_member and own_member.id == obligation.member_id)
        if not (user.is_superuser or user.role in PAYMENT_COLLECTING_ROLES or is_desk_worker_for(user, funeral, "contributions") or is_own_obligation):
            return Response(
                {"detail": "You're not assigned to this funeral's contributions desk, and this isn't your own contribution."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = RecordPaymentSerializer(data=request.data, context={"request": request, "obligation": obligation})
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        return Response(ContributionPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class RequestPaymentReversalView(APIView):
    """'An authorized administrator should be able to initiate a reversal or correction' — request step only, community-scoped so nobody can reach into another community's payments."""
    permission_classes = [IsAuthenticated]

    def post(self, request, payment_id):
        payment = get_object_or_404(ContributionPayment, id=payment_id)
        if not request.user.is_superuser and payment.obligation.funeral_event.community_id != request.user.community_id:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = RequestPaymentReversalSerializer(data=request.data, context={"payment": payment, "request": request})
        serializer.is_valid(raise_exception=True)
        reversal = serializer.save()
        return Response(PaymentReversalSerializer(reversal).data, status=status.HTTP_201_CREATED)


class ListPaymentReversalsView(APIView):
    """Every reversal request for the acting user's own community — pending, approved, and rejected alike, the full record."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            reversals = services.list_reversal_requests(community=request.user.community, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": exc.messages}, status=status.HTTP_403_FORBIDDEN)
        return Response(PaymentReversalSerializer(reversals, many=True).data)


class _DecidePaymentReversalView(APIView):
    permission_classes = [IsAuthenticated, RequiresExecutiveContext]
    approve: bool

    def post(self, request, reversal_id):
        from .models import PaymentReversal
        reversal = get_object_or_404(PaymentReversal, id=reversal_id)
        if not request.user.is_superuser and reversal.payment.obligation.funeral_event.community_id != request.user.community_id:
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = DecidePaymentReversalSerializer(
            data=request.data, context={"reversal": reversal, "request": request, "approve": self.approve},
        )
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        return Response(PaymentReversalSerializer(updated).data)


class ApprovePaymentReversalView(_DecidePaymentReversalView):
    approve = True


class RejectPaymentReversalView(_DecidePaymentReversalView):
    approve = False


class PendingDeskAssignmentsView(APIView):
    """
    'It has to be approved by the community admin or temporary admin.'
    A Community (or Temporary) Admin's own approval queue — every
    Family desk assignment awaiting their sign-off, across every
    funeral in their own community.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not (request.user.is_superuser or request.user.role == "community_admin"):
            return Response({"detail": "Only a Community Administrator has a desk-assignment approval queue."}, status=403)
        pending = services.list_pending_desk_assignments(request.user.community)
        from .serializers import DeskAssignmentSerializer
        return Response(DeskAssignmentSerializer(pending, many=True).data)


class ApproveDeskAssignmentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, assignment_id):
        from .models import FuneralDeskAssignment
        qs = FuneralDeskAssignment.objects.all() if request.user.is_superuser else FuneralDeskAssignment.objects.filter(funeral_event__community=request.user.community)
        assignment = get_object_or_404(qs, id=assignment_id)
        try:
            updated = services.approve_desk_assignment(assignment=assignment, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        from .serializers import DeskAssignmentSerializer
        return Response(DeskAssignmentSerializer(updated).data)
