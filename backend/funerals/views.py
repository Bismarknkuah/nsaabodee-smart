from decimal import Decimal, InvalidOperation

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
    RecordPaymentsAcrossActiveFuneralsSerializer,
    ActivateAsupedeSerializer,
    AppointCommitteePositionSerializer,
    AssignDeskWorkerSerializer,
    AsupedeObligationSerializer,
    AsupedePaymentSerializer,
    ContributionObligationSerializer,
    ContributionPaymentSerializer,
    DecidePaymentReversalSerializer,
    DeskAssignmentSerializer,
    FuneralCommitteePositionSerializer,
    FuneralEventCreateSerializer,
    FuneralEventSerializer,
    InLawContributionRequestSerializer,
    InLawObligationSerializer,
    InLawPaymentSerializer,
    ManageMemorialPageSerializer,
    MemberRateOverrideSerializer,
    PaymentReversalSerializer,
    RecordAsupedePaymentSerializer,
    RecordInLawPaymentSerializer,
    RecordPaymentSerializer,
    RequestFuneralEventSerializer,
    RequestInLawContributionSerializer,
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

    @action(
        detail=True, methods=["post"], url_path=r"obligations/(?P<obligation_id>[^/.]+)/apply-wallet",
        permission_classes=[IsAuthenticated, CanRecordPaymentsOrIsDeskWorker, RequiresExecutiveContext, IsSameCommunity],
    )
    def apply_wallet(self, request, id=None, obligation_id=None):
        """Spending an existing wallet credit toward this obligation — same authorization as recording any other payment."""
        funeral = self.get_object()
        user = request.user
        obligation = get_object_or_404(ContributionObligation, id=obligation_id, funeral_event=funeral)

        from .permissions import PAYMENT_COLLECTING_ROLES
        own_member = getattr(user, "member_profile", None)
        is_own_obligation = bool(own_member and own_member.id == obligation.member_id)
        if not (user.is_superuser or user.role in PAYMENT_COLLECTING_ROLES or is_desk_worker_for(user, funeral, "contributions") or is_own_obligation):
            return Response(
                {"detail": "You're not assigned to this funeral's contributions desk, and this isn't your own contribution."},
                status=status.HTTP_403_FORBIDDEN,
            )
        try:
            amount = Decimal(str(request.data.get("amount", "0")))
        except Exception:
            return Response({"detail": "Provide a valid amount."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            payment = services.apply_wallet_to_obligation(obligation=obligation, amount=amount, actor=user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ContributionPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="asupede/activate", permission_classes=[IsAuthenticated, RequiresExecutiveContext, IsSameCommunity])
    def activate_asupede(self, request, id=None):
        """'The funeral should have enough information for the system to identify the relevant collection period.'"""
        funeral = self.get_object()
        serializer = ActivateAsupedeSerializer(data=request.data, context={"request": request, "funeral": funeral})
        serializer.is_valid(raise_exception=True)
        obligations = serializer.save()
        return Response(AsupedeObligationSerializer(obligations, many=True).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="asupede/obligations", permission_classes=[IsAuthenticated, IsSameCommunity])
    def asupede_obligations(self, request, id=None):
        funeral = self.get_object()
        return Response(AsupedeObligationSerializer(funeral.asupede_obligations.select_related("member").all(), many=True).data)

    @action(detail=True, methods=["get"], url_path="asupede/summary", permission_classes=[IsAuthenticated, IsSameCommunity])
    def asupede_summary(self, request, id=None):
        """'For each funeral, authorized users should be able to see a complete contribution overview' — the Asupedeɛ slice of it."""
        funeral = self.get_object()
        return Response(services.asupede_summary(funeral))

    @action(
        detail=True, methods=["post"], url_path=r"asupede-obligations/(?P<obligation_id>[^/.]+)/record-payment",
        permission_classes=[IsAuthenticated, CanRecordPaymentsOrIsDeskWorker, RequiresExecutiveContext, IsSameCommunity],
    )
    def record_asupede_payment(self, request, id=None, obligation_id=None):
        """Same collecting-role/desk-worker/self-payment authorization as the mandatory ledger's own record_payment — Asupedeɛ isn't a separately-permissioned action."""
        funeral = self.get_object()
        user = request.user
        from .models import AsupedeObligation
        obligation = get_object_or_404(AsupedeObligation, id=obligation_id, funeral_event=funeral)

        from .permissions import PAYMENT_COLLECTING_ROLES
        own_member = getattr(user, "member_profile", None)
        is_own_obligation = bool(own_member and own_member.id == obligation.member_id)
        if not (user.is_superuser or user.role in PAYMENT_COLLECTING_ROLES or is_desk_worker_for(user, funeral, "contributions") or is_own_obligation):
            return Response(
                {"detail": "You're not assigned to this funeral's contributions desk, and this isn't your own contribution."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = RecordAsupedePaymentSerializer(data=request.data, context={"request": request, "obligation": obligation})
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        return Response(AsupedePaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get", "post"], url_path="in-law-requests", permission_classes=[IsAuthenticated, IsSameCommunity])
    def in_law_requests(self, request, id=None):
        """
        GET -> every In-Law contribution request for this funeral.
        POST -> 'the deceased family should be able to initiate an
        In-Law Contribution Request.' The authorization failure is
        caught here directly (403) rather than delegated to the
        serializer's own exception handling (which DRF always turns
        into a 400) — the same "wrong role, not bad input" distinction
        already established for TownElderPerTitleRatesView.
        services.request_in_law_contribution's own, more precise
        role check (_IN_LAW_REQUEST_ROLES) is the actual authority
        here, not a separate, redundant permission class.
        """
        funeral = self.get_object()
        if request.method == "GET":
            return Response(InLawContributionRequestSerializer(services.list_in_law_requests(funeral=funeral), many=True).data)

        from django.core.exceptions import ValidationError as DjangoValidationError
        input_serializer = RequestInLawContributionSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        from families.models import Family
        try:
            in_law_family = Family.objects.get(id=input_serializer.validated_data["in_law_family_id"], community=request.user.community)
        except Family.DoesNotExist:
            return Response({"in_law_family_id": "Family not found in this community."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            in_law_request = services.request_in_law_contribution(
                funeral=funeral, in_law_family=in_law_family, relationship=input_serializer.validated_data["relationship"],
                requested_amount=input_serializer.validated_data["requested_amount"], reason=input_serializer.validated_data.get("reason", ""),
                actor=request.user,
            )
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(InLawContributionRequestSerializer(in_law_request).data, status=status.HTTP_201_CREATED)

    @action(
        detail=True, methods=["post"], url_path=r"in-law-requests/(?P<request_id>[^/.]+)/decide",
        permission_classes=[IsAuthenticated, RequiresExecutiveContext, IsSameCommunity],
    )
    def decide_in_law_request(self, request, id=None, request_id=None):
        """'The request should go through the configured approval process.'"""
        funeral = self.get_object()
        from django.core.exceptions import ValidationError as DjangoValidationError

        from .models import InLawContributionRequest
        in_law_request = get_object_or_404(InLawContributionRequest, id=request_id, funeral_event=funeral)
        decision = request.data.get("decision", "")
        try:
            updated = services.decide_in_law_contribution_request(request=in_law_request, actor=request.user, decision=decision)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(InLawContributionRequestSerializer(updated).data)

    @action(
        detail=True, methods=["post"], url_path=r"in-law-obligations/(?P<obligation_id>[^/.]+)/record-payment",
        permission_classes=[IsAuthenticated, CanRecordPaymentsOrIsDeskWorker, RequiresExecutiveContext, IsSameCommunity],
    )
    def record_in_law_payment(self, request, id=None, obligation_id=None):
        """Same collecting-role/desk-worker authorization as every other ledger's own record_payment — no self-payment exception here, since this obligation belongs to a whole family, not one individual."""
        funeral = self.get_object()
        user = request.user
        from .models import InLawObligation
        obligation = get_object_or_404(InLawObligation, id=obligation_id, funeral_event=funeral)

        from .permissions import PAYMENT_COLLECTING_ROLES
        if not (user.is_superuser or user.role in PAYMENT_COLLECTING_ROLES or is_desk_worker_for(user, funeral, "contributions")):
            return Response(
                {"detail": "You're not assigned to this funeral's contributions desk."},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = RecordInLawPaymentSerializer(data=request.data, context={"request": request, "obligation": obligation})
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        return Response(InLawPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class RecordPaymentsAcrossActiveFuneralsView(APIView):
    """
    'The system should be more efficient and friendly, so it can be
    faster' — one submission settles a member's outstanding balance
    across every currently active funeral, instead of a collector
    repeating the same search-and-submit once per funeral. Same
    authorization as recording any single payment.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .permissions import PAYMENT_COLLECTING_ROLES
        if not (request.user.is_superuser or request.user.role in PAYMENT_COLLECTING_ROLES):
            return Response({"detail": "Only a Collector (or Superuser) can record payments across multiple funerals at once."}, status=status.HTTP_403_FORBIDDEN)
        serializer = RecordPaymentsAcrossActiveFuneralsSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        payments = serializer.save()
        return Response(ContributionPaymentSerializer(payments, many=True).data, status=status.HTTP_201_CREATED)


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
    'The family treasurer needs the approval of the family secretary
    and the family head... the community treasurer also needs the
    community chairman and the secretary to approve.' This person's
    own approval queue — whoever they are among the roles eligible to
    approve something.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        pending = services.list_pending_desk_assignments_for(request.user)
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


def _serialize_ledger_wallet(wallet):
    return {
        "id": str(wallet.id),
        "scope": wallet.scope,
        "scope_display": wallet.get_scope_display(),
        "family_id": str(wallet.family_id) if wallet.family_id else None,
        "family_name": wallet.family.name if wallet.family_id else None,
        "balance": str(wallet.balance),
        "updated_at": wallet.updated_at.isoformat(),
    }


def _serialize_ledger_wallet_transaction(t):
    return {
        "id": str(t.id),
        "kind": t.kind,
        "amount": str(t.amount),
        "note": t.note,
        "source_payment_receipt": t.source_payment.receipt_number if t.source_payment_id else None,
        "actor_username": t.actor.username if t.actor_id else None,
        "created_at": t.created_at.isoformat(),
    }


class LedgerWalletsView(APIView):
    """
    'Each family should have their wallet being managed by the family
    treasurer... the town leader should also have their wallet as
    well.' GET -> every Ledger Wallet this account is authorized to
    see — see services.ledger_wallets_for for the exact scoping rule.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallets = services.ledger_wallets_for(actor=request.user)
        return Response([_serialize_ledger_wallet(w) for w in wallets])


class LedgerWalletTransactionsView(APIView):
    """GET -> the full, auditable transaction history for one wallet — 'transparent since it's a transaction aspect.'"""
    permission_classes = [IsAuthenticated]

    def get(self, request, wallet_id):
        wallet = get_object_or_404(services.ledger_wallets_for(actor=request.user), id=wallet_id)
        transactions = services.list_ledger_wallet_transactions(wallet=wallet)
        return Response([_serialize_ledger_wallet_transaction(t) for t in transactions])


class LedgerWalletWithdrawView(APIView):
    """POST {amount, note} -> withdraws from one wallet — always its own DEBIT transaction, never a silent balance edit."""
    permission_classes = [IsAuthenticated]

    def post(self, request, wallet_id):
        wallet = get_object_or_404(services.ledger_wallets_for(actor=request.user), id=wallet_id)
        try:
            amount = Decimal(str(request.data.get("amount", "")))
        except InvalidOperation:
            return Response({"detail": "'amount' must be a number."}, status=status.HTTP_400_BAD_REQUEST)
        note = request.data.get("note", "")
        try:
            updated = services.withdraw_from_ledger_wallet(wallet=wallet, amount=amount, note=note, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(_serialize_ledger_wallet(updated))
