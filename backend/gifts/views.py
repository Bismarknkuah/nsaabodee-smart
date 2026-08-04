from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from funerals.models import FuneralEvent
from members.models import Member
from . import services
from .models import DonationAccountRegistration, GiftDonation
from .permissions import GIFT_RECORDING_ROLES, is_family_head_of
from .serializers import (
    DonationAccountRegistrationSerializer,
    GiftDonationSerializer,
    MaskedGiftDonationSerializer,
    RecordGiftDonationSerializer,
    RegisterDonationAccountHolderSerializer,
)


def _get_funeral(request, funeral_id):
    qs = FuneralEvent.objects.all() if request.user.is_superuser else FuneralEvent.objects.filter(community=request.user.community)
    return get_object_or_404(qs, id=funeral_id)


def _can_view_gift_ledger(user, funeral) -> bool:
    """
    "The funeral committee should have access to all the money paid
    except the donations" — but a Community Administrator is the one
    role with genuine platform-level oversight responsibility (fraud
    review, disputes, audits), distinct from the rest of the funeral
    committee (Treasurer, Chairman, Secretary, etc.), who are excluded
    from Ledger 2 the same way everyone else is. `user.can_manage_families()`
    is the same "Community Admin and above" check used everywhere else
    in this platform for admin-tier actions.
    """
    return user.is_superuser or user.can_manage_families() or is_family_head_of(user, funeral.deceased_family)


def _should_mask_donor_pii(user, funeral) -> bool:
    """
    'They must not have access to the private information of
    individuals who register solely to make gift donations unless...
    required for reconciliation, auditing, or legal compliance.' Only
    a temporary/rental event's own Community Admin is masked by
    default — a superuser, and a family head viewing their own
    family's donations (an already-established, separate access path),
    are unaffected, and so is any Community Admin of an ordinary,
    permanent community.
    """
    if user.is_superuser:
        return False
    return funeral.community.is_temporary_event and user.role == "community_admin"


def _can_record_gifts(user) -> bool:
    return user.is_superuser or user.role in GIFT_RECORDING_ROLES


class GiftDonationListCreateView(APIView):
    """
    GET  /api/funerals/{funeral_id}/gifts/   — this funeral's gift ledger (Ledger 2).
                                                Restricted to this family's own head or
                                                a superuser — NOT the general funeral
                                                committee, per the master brief.
    POST /api/funerals/{funeral_id}/gifts/   — record a new donation (any collecting role).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, funeral_id):
        funeral = _get_funeral(request, funeral_id)
        if not _can_view_gift_ledger(request.user, funeral):
            return Response({"detail": "Only this family's own head can view its gift ledger."}, status=403)

        donations = funeral.gift_donations.select_related("recipient_family", "donor_member", "received_by_member")
        category = request.query_params.get("category")
        if category:
            donations = donations.filter(donor_category=category)
        from nsaabodeeq.pagination import paginate_response
        serializer_class = MaskedGiftDonationSerializer if _should_mask_donor_pii(request.user, funeral) else GiftDonationSerializer
        return paginate_response(request, donations, serializer_class)

    def post(self, request, funeral_id):
        funeral = _get_funeral(request, funeral_id)
        from funerals.permissions import is_desk_worker_for
        if not (_can_record_gifts(request.user) or is_desk_worker_for(request.user, funeral, "gifts")):
            return Response({"detail": "You don't have permission to record gift donations."}, status=403)
        serializer = RecordGiftDonationSerializer(data=request.data, context={"request": request, "funeral": funeral})
        serializer.is_valid(raise_exception=True)
        donation = serializer.save()
        return Response(GiftDonationSerializer(donation).data, status=status.HTTP_201_CREATED)


class GiftDonationReconciliationView(APIView):
    """
    'Unless that information is required for reconciliation, auditing,
    or legal compliance.' The one deliberate, explicit exception to the
    masking above — full donor detail, for a genuine, named reason, and
    always logged: accessing this is itself an auditable act, not a
    silent bypass of the privacy boundary GiftDonationListCreateView
    otherwise enforces for a temporary event's own Community Admin.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, funeral_id):
        funeral = _get_funeral(request, funeral_id)
        if not _can_view_gift_ledger(request.user, funeral):
            return Response({"detail": "Only this family's own head can view its gift ledger."}, status=403)

        reason = request.query_params.get("reason", "").strip()
        if not reason:
            return Response({"detail": "A reason (reconciliation, auditing, or legal compliance) is required to view unmasked donor detail."}, status=400)

        donations = funeral.gift_donations.select_related("recipient_family", "donor_member", "received_by_member")
        from audit_log.services import record_event
        record_event(
            category="funeral_opening", action="donor_pii_reconciliation_access", actor=request.user, community=funeral.community,
            target_type="FuneralEvent", target_id=funeral.id, target_label=funeral.deceased_name,
            description=f"'{request.user.username}' viewed unmasked donor detail for {funeral.deceased_name}'s funeral. Reason given: {reason}",
        )
        from nsaabodeeq.pagination import paginate_response
        return paginate_response(request, donations, GiftDonationSerializer)


class GiftSummaryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, funeral_id):
        funeral = _get_funeral(request, funeral_id)
        if not _can_view_gift_ledger(request.user, funeral):
            return Response({"detail": "Only this family's own head can view its gift ledger."}, status=403)
        return Response(services.gift_summary(funeral))


class GiftCategoryBreakdownView(APIView):
    """
    GET -> the guest/town-leader/other split of this funeral's gift
    ledger — "the system should know the total amount received from
    guests [and] elders of the town" made concrete.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, funeral_id):
        funeral = _get_funeral(request, funeral_id)
        if not _can_view_gift_ledger(request.user, funeral):
            return Response({"detail": "Only this family's own head can view its gift ledger."}, status=403)
        return Response(services.donations_by_category(funeral))


class DonationAccountRegistrationListCreateView(APIView):
    """
    GET  -> everyone in the community can see WHO is registered to
            receive donations for this funeral (this is a name list, not
            a money amount — no reason to hide it, and a guest/cashier
            needs to see these names to pick from when recording a gift).
    POST -> register a member as a donation-account holder. Restricted to
            the same roles who could record a gift in the first place,
            plus this family's own head (he's the one who'd know who to
            trust with his family's donations).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, funeral_id):
        funeral = _get_funeral(request, funeral_id)
        registrations = services.list_donation_account_holders(funeral)
        return Response(DonationAccountRegistrationSerializer(registrations, many=True).data)

    def post(self, request, funeral_id):
        funeral = _get_funeral(request, funeral_id)
        allowed = _can_record_gifts(request.user) or is_family_head_of(request.user, funeral.deceased_family)
        if not allowed:
            return Response({"detail": "You don't have permission to register a donation-account holder."}, status=403)

        serializer = RegisterDonationAccountHolderSerializer(data=request.data, context={"request": request, "funeral": funeral})
        serializer.is_valid(raise_exception=True)
        registration = serializer.save()
        return Response(DonationAccountRegistrationSerializer(registration).data, status=status.HTTP_201_CREATED)


class PendingDonationAccountRegistrationsView(APIView):
    """
    'Activated when the family heads approve it' — a Family Head's own
    approval queue, every registration awaiting their sign-off, across
    every funeral their own family members are registered for.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        own_member = getattr(request.user, "member_profile", None)
        if own_member is None or own_member.family_id is None or own_member.family.family_head_id != own_member.id:
            return Response({"detail": "Only a Family Head has a donation-account approval queue."}, status=403)
        pending = services.list_pending_donation_account_registrations(own_member.family)
        return Response(DonationAccountRegistrationSerializer(pending, many=True).data)


class ApproveDonationAccountRegistrationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, registration_id):
        registration = get_object_or_404(DonationAccountRegistration, id=registration_id, community=request.user.community)
        try:
            updated = services.approve_donation_account_registration(registration=registration, actor=request.user)
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(DonationAccountRegistrationSerializer(updated).data)


class MyDonationsReceivedView(APIView):
    """
    GET -> everything ever attributed to MY OWN linked Member profile as
    a donation receiver, across every funeral — the personal
    accountability view every registered receiver can always see for
    themselves, regardless of role, since it's their own data.

    ?export=pdf -> the same data as a printable statement (donor name,
    phone, hometown, amount) — "after the funeral, all should be able
    to print receipts to all those who received donations."
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        member = getattr(request.user, "member_profile", None)
        if member is None:
            empty = {"member_id": None, "member_name": None, "total_received": "0", "donation_count": 0, "by_funeral": [], "entries": []}
            return Response(empty)

        received = services.donations_received_by_member(member)
        if request.query_params.get("export") == "pdf":
            from django.http import HttpResponse
            from reports.pdf import donation_receiver_statement_pdf
            pdf_bytes = donation_receiver_statement_pdf(
                community_name=member.community.name, member_name=member.full_name, entries=received["entries"],
            )
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="donations-received-{member.full_name}.pdf"'
            return response
        return Response(received)


class AllReceiversDonationStatementView(APIView):
    """
    GET -> every registered receiver for this funeral, each with their
    own donor list — the family head/admin oversight version of
    MyDonationsReceivedView. Same visibility tier as the rest of Ledger
    2 (this family's own head, Community Admin+, or a superuser) —
    "the funeral committee should have access to all the money paid
    except the donations" applies here exactly as everywhere else.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, funeral_id):
        funeral = _get_funeral(request, funeral_id)
        if not _can_view_gift_ledger(request.user, funeral):
            return Response({"detail": "Only this family's own head can view its donation receivers."}, status=403)

        receivers = services.all_receivers_donation_lists(funeral)
        if request.query_params.get("export") == "pdf":
            from django.http import HttpResponse
            from reports.pdf import all_receivers_donation_statement_pdf
            pdf_bytes = all_receivers_donation_statement_pdf(
                community_name=funeral.community.name, deceased_name=funeral.deceased_name, receivers=receivers,
            )
            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = f'inline; filename="donation-receivers-{funeral.deceased_name}.pdf"'
            return response
        return Response(receivers)
