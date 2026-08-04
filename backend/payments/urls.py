from django.urls import path

from .views import (
    InitiateMomoGiftPaymentView,
    InitiateMomoPaymentView,
    MomoPaymentStatusView,
    PaystackWebhookView,
    SubmitMomoOtpView,
)

urlpatterns = [
    path("payments/momo/request-to-pay/", InitiateMomoPaymentView.as_view(), name="momo-request-to-pay"),
    path("payments/momo/gift-request-to-pay/", InitiateMomoGiftPaymentView.as_view(), name="momo-gift-request-to-pay"),
    path("payments/momo/status/<uuid:reference_id>/", MomoPaymentStatusView.as_view(), name="momo-status"),
    path("payments/momo/submit-otp/<uuid:reference_id>/", SubmitMomoOtpView.as_view(), name="momo-submit-otp"),
    path("payments/paystack/webhook/", PaystackWebhookView.as_view(), name="paystack-webhook"),
]
