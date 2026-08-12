from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .models import MomoPaymentRequest
from .providers import verify_paystack_webhook_signature
from .serializers import InitiateMomoGiftPaymentSerializer, InitiateMomoPaymentSerializer, MomoPaymentRequestSerializer, SubmitMomoOtpSerializer


class InitiateMomoPaymentView(APIView):
    """POST {obligation_id, phone_number, amount} -> a pending MomoPaymentRequest. Prompts the payer's phone to authorize via Mobile Money."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = InitiateMomoPaymentSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        momo_request = serializer.save()
        return Response(MomoPaymentRequestSerializer(momo_request).data, status=status.HTTP_201_CREATED)


class InitiateMomoGiftPaymentView(APIView):
    """
    POST {funeral_id, phone_number, amount, donor_name, received_by_member_id?}
    -> a pending MomoPaymentRequest for a gift/donation. Anyone authenticated
    can initiate this (a guest paying isn't a registered member, but
    whoever operates the collecting device — a cashier — is).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = InitiateMomoGiftPaymentSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        momo_request = serializer.save()
        return Response(MomoPaymentRequestSerializer(momo_request).data, status=status.HTTP_201_CREATED)


class SubmitMomoOtpView(APIView):
    """POST {otp} -> the one extra step MTN mobile money (via Paystack) needs when a request comes back 'awaiting_otp'."""
    permission_classes = [IsAuthenticated]

    def post(self, request, reference_id):
        qs = MomoPaymentRequest.objects.all() if request.user.is_superuser else MomoPaymentRequest.objects.filter(community=request.user.community)
        momo_request = get_object_or_404(qs, reference_id=reference_id)
        serializer = SubmitMomoOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            updated = services.submit_momo_otp(request=momo_request, otp=serializer.validated_data["otp"])
        except DjangoValidationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MomoPaymentRequestSerializer(updated).data)


class MomoPaymentStatusView(APIView):
    """GET -> polls Paystack for the real outcome and finalizes (records the real payment) the moment it clears. A fallback alongside the webhook, not the primary path — see PaystackWebhookView."""
    permission_classes = [IsAuthenticated]

    def get(self, request, reference_id):
        qs = MomoPaymentRequest.objects.all() if request.user.is_superuser else MomoPaymentRequest.objects.filter(community=request.user.community)
        momo_request = get_object_or_404(qs, reference_id=reference_id)
        updated = services.check_and_finalize_momo_payment(momo_request)
        return Response(MomoPaymentRequestSerializer(updated).data)


@method_decorator(csrf_exempt, name="dispatch")
class PaystackWebhookView(APIView):
    """
    POST — Paystack's own server calls this the moment a charge's real
    outcome is known ('charge.success' once mobile money is actually
    authorized offline, or a failure event). Deliberately public
    (Paystack itself, not a logged-in user, is the caller) but never
    trusts the body without first verifying 'x-paystack-signature' —
    see providers.verify_paystack_webhook_signature. Always returns 200
    once the signature check passes, even for an event this platform
    doesn't otherwise act on, since Paystack retries a webhook call
    that doesn't get a 2xx response.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        signature = request.headers.get("x-paystack-signature", "")
        if not verify_paystack_webhook_signature(raw_body=request.body, signature_header=signature):
            return HttpResponse(status=401)

        event = request.data.get("event", "")
        data = request.data.get("data", {})
        reference = data.get("reference")
        if not reference:
            return HttpResponse(status=200)

        try:
            momo_request = MomoPaymentRequest.objects.filter(reference_id=reference).first()
        except DjangoValidationError:
            return HttpResponse(status=200)  # not a real UUID at all — can't be one of ours, nothing to do
        if momo_request is None:
            return HttpResponse(status=200)  # not one of ours, or already deleted — nothing to do

        if event == "charge.success":
            services.check_and_finalize_momo_payment(momo_request)
        elif event == "charge.failed" and momo_request.status in (MomoPaymentRequest.Status.PENDING, MomoPaymentRequest.Status.AWAITING_OTP):
            momo_request.status = MomoPaymentRequest.Status.FAILED
            momo_request.provider_response = "charge.failed webhook"
            momo_request.save(update_fields=["status", "provider_response", "updated_at"])
        return HttpResponse(status=200)
