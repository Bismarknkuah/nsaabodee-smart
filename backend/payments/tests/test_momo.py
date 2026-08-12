import hashlib
import hmac
import json
from decimal import Decimal
from unittest import mock
from unittest.mock import MagicMock

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import Role, User
from families import services as family_services
from funerals import services as funeral_services
from gifts import services as gift_services
from gifts.models import GiftDonation
from members import services as member_services
from payments import services as payment_services
from payments.models import MomoPaymentRequest
from payments.providers import MomoProviderError, PaystackMomoProvider, ProviderNotConfiguredError, verify_paystack_webhook_signature
from tenants.models import Community


class PaystackMomoProviderTests(TestCase):
    def test_raises_when_not_configured(self):
        with self.assertRaises(ProviderNotConfiguredError):
            PaystackMomoProvider().request_to_pay(reference_id="abc", amount="10", phone_number="+233200000000")

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_fake")
    def test_request_to_pay_builds_a_correct_charge_request(self):
        mock_post = MagicMock(return_value=MagicMock(
            status_code=200, json=lambda: {"status": True, "data": {"status": "pay_offline", "reference": "ref-1"}}
        ))
        provider = PaystackMomoProvider(http_post=mock_post)
        result = provider.request_to_pay(reference_id="ref-1", amount="50", phone_number="+233200000000", payer_message="Contribution")

        self.assertEqual(result["status"], "pay_offline")
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["reference"], "ref-1")
        self.assertEqual(kwargs["json"]["mobile_money"]["phone"], "+233200000000")
        self.assertEqual(kwargs["json"]["mobile_money"]["provider"], "mtn")
        self.assertEqual(kwargs["json"]["currency"], "GHS")
        # Paystack requires the smallest subunit (pesewas) — 50 cedis is 5000 pesewas.
        self.assertEqual(kwargs["json"]["amount"], "5000")
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer sk_test_fake")

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_fake")
    def test_check_status_translates_paystack_success_to_the_platforms_own_vocabulary(self):
        mock_get = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"data": {"status": "success"}}))
        provider = PaystackMomoProvider(http_get=mock_get)
        self.assertEqual(provider.check_status(reference_id="ref-1"), "SUCCESSFUL")

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_fake")
    def test_check_status_translates_paystack_failed(self):
        mock_get = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"data": {"status": "failed"}}))
        provider = PaystackMomoProvider(http_get=mock_get)
        self.assertEqual(provider.check_status(reference_id="ref-1"), "FAILED")

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_fake")
    def test_check_status_treats_any_other_paystack_status_as_still_pending(self):
        mock_get = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"data": {"status": "pay_offline"}}))
        provider = PaystackMomoProvider(http_get=mock_get)
        self.assertEqual(provider.check_status(reference_id="ref-1"), "PENDING")

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_fake")
    def test_submit_otp_builds_a_correct_request(self):
        mock_post = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"data": {"status": "success"}}))
        provider = PaystackMomoProvider(http_post=mock_post)
        result = provider.submit_otp(reference_id="ref-1", otp="123456")
        self.assertEqual(result["status"], "success")
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"], {"otp": "123456", "reference": "ref-1"})


class PaystackWebhookSignatureTests(TestCase):
    @override_settings(PAYSTACK_SECRET_KEY="sk_test_fake")
    def test_a_correctly_signed_body_verifies(self):
        body = b'{"event": "charge.success"}'
        signature = hmac.new(b"sk_test_fake", body, hashlib.sha512).hexdigest()
        self.assertTrue(verify_paystack_webhook_signature(raw_body=body, signature_header=signature))

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_fake")
    def test_a_tampered_body_fails_verification(self):
        body = b'{"event": "charge.success"}'
        signature = hmac.new(b"sk_test_fake", b'{"event": "something_else"}', hashlib.sha512).hexdigest()
        self.assertFalse(verify_paystack_webhook_signature(raw_body=body, signature_header=signature))

    def test_verification_fails_outright_when_unconfigured(self):
        self.assertFalse(verify_paystack_webhook_signature(raw_body=b"{}", signature_header="anything"))


class MomoPaymentFlowTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        from funerals.models import ContributionObligation
        self.obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)

    def test_initiate_payment_fails_cleanly_without_credentials(self):
        with self.assertRaises(ValidationError):
            payment_services.initiate_momo_payment(obligation=self.obligation, phone_number="+233200000000", amount=Decimal("50"))
        # And it's recorded as a failed attempt, not silently discarded.
        self.assertEqual(MomoPaymentRequest.objects.filter(obligation=self.obligation).first().status, MomoPaymentRequest.Status.FAILED)

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_fake")
    def test_momo_also_accepts_more_than_the_required_amount(self):
        """The minimum-not-ceiling rule applies to Mobile Money the same as cash — nothing MoMo-specific should re-introduce a cap."""
        with self._patch_provider(http_post=self._pay_offline_response()):
            momo_request = payment_services.initiate_momo_payment(
                obligation=self.obligation, phone_number="+233200000000", amount=Decimal("500")
            )
        self.assertEqual(momo_request.amount, Decimal("500"))

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_fake")
    def test_successful_momo_request_flows_through_to_a_real_recorded_payment(self):
        with self._patch_provider(http_post=self._pay_offline_response()):
            momo_request = payment_services.initiate_momo_payment(
                obligation=self.obligation, phone_number="+233200000000", amount=Decimal("50"), initiated_by=self.admin
            )
        self.assertEqual(momo_request.status, MomoPaymentRequest.Status.PENDING)

        with self._patch_provider(http_get=self._status_response("success")):
            finalized = payment_services.check_and_finalize_momo_payment(momo_request)

        self.assertEqual(finalized.status, MomoPaymentRequest.Status.SUCCESSFUL)
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.amount_paid, Decimal("50"))
        self.assertEqual(self.obligation.payment_status, "paid")

        # Polling again after it's already finalized must never double-credit.
        with self._patch_provider(http_get=self._status_response("success")):
            payment_services.check_and_finalize_momo_payment(finalized)
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.amount_paid, Decimal("50"))

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_fake")
    def test_an_mtn_charge_needing_an_otp_lands_in_awaiting_otp_status(self):
        """'send_otp' is MTN mobile money's own extra step via Paystack."""
        mock_post = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"data": {"status": "send_otp"}}))
        with self._patch_provider(http_post=mock_post):
            momo_request = payment_services.initiate_momo_payment(
                obligation=self.obligation, phone_number="+233200000000", amount=Decimal("50")
            )
        self.assertEqual(momo_request.status, MomoPaymentRequest.Status.AWAITING_OTP)

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_fake")
    def test_submitting_the_correct_otp_finalizes_the_payment(self):
        mock_post = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"data": {"status": "send_otp"}}))
        with self._patch_provider(http_post=mock_post):
            momo_request = payment_services.initiate_momo_payment(
                obligation=self.obligation, phone_number="+233200000000", amount=Decimal("50")
            )

        mock_otp_post = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"data": {"status": "success"}}))
        with self._patch_provider(http_post=mock_otp_post):
            finalized = payment_services.submit_momo_otp(request=momo_request, otp="123456")

        self.assertEqual(finalized.status, MomoPaymentRequest.Status.SUCCESSFUL)
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.amount_paid, Decimal("50"))

    def test_submitting_an_otp_when_none_was_ever_requested_is_rejected(self):
        momo_request = MomoPaymentRequest.objects.create(
            community=self.bodi, target_type=MomoPaymentRequest.TargetType.CONTRIBUTION,
            obligation=self.obligation, phone_number="+233200000000", amount=Decimal("50"),
            status=MomoPaymentRequest.Status.PENDING,
        )
        with self.assertRaises(ValidationError):
            payment_services.submit_momo_otp(request=momo_request, otp="123456")

    def _pay_offline_response(self):
        return MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"data": {"status": "pay_offline"}}))

    def _status_response(self, paystack_status):
        return MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"data": {"status": paystack_status}}))

    def _patch_provider(self, http_post=None, http_get=None):
        return mock.patch("payments.services.PaystackMomoProvider", return_value=PaystackMomoProvider(http_post=http_post, http_get=http_get))


class MomoGiftPaymentTests(TestCase):
    """The Ledger 2 (gift/donation) side of Mobile Money — 'some people can also pay via momo.'"""

    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi")
        self.admin = User.objects.create_user(username="admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Yaw Asona", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        self.head_member = member_services.register_member(community=self.bodi, full_name="Gift Test Head", gender="male", family=self.asona)
        self.head_user = User.objects.create_user(username="gift_momo_head", password="x", community=self.bodi, role=Role.FAMILY_HEAD)
        member_services.link_member_to_user(member=self.head_member, user=self.head_user, actor=self.admin)
        family_services.assign_family_head(family=self.asona, member=self.head_member, actor=self.admin)
        self.receiver_member = member_services.register_member(community=self.bodi, full_name="Kojo", gender="male", family=self.asona)

    def test_gift_momo_request_requires_donation_account_registration_if_receiver_specified(self):
        with self.assertRaises(ValidationError):
            payment_services.initiate_momo_gift_payment(
                funeral=self.funeral, phone_number="+233200000000", amount=Decimal("50"),
                donor_name="A Guest", received_by_member=self.receiver_member,
            )

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_fake")
    def test_successful_gift_momo_request_becomes_a_real_gift_donation_earmarked_to_the_receiver(self):
        gift_services.register_donation_account_holder(funeral=self.funeral, member=self.receiver_member, actor=self.head_user)

        mock_post = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"data": {"status": "pay_offline"}}))
        with mock.patch("payments.services.PaystackMomoProvider", return_value=PaystackMomoProvider(http_post=mock_post)):
            momo_request = payment_services.initiate_momo_gift_payment(
                funeral=self.funeral, phone_number="+233200000000", amount=Decimal("100"),
                donor_name="A Generous Guest", received_by_member=self.receiver_member,
            )
        self.assertEqual(momo_request.target_type, MomoPaymentRequest.TargetType.GIFT)
        self.assertEqual(momo_request.status, MomoPaymentRequest.Status.PENDING)

        mock_get = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"data": {"status": "success"}}))
        with mock.patch("payments.services.PaystackMomoProvider", return_value=PaystackMomoProvider(http_get=mock_get)):
            finalized = payment_services.check_and_finalize_momo_payment(momo_request)
        self.assertEqual(finalized.status, MomoPaymentRequest.Status.SUCCESSFUL)

        donation = GiftDonation.objects.get(funeral_event=self.funeral, donor_name="A Generous Guest")
        self.assertEqual(donation.received_by_member_id, self.receiver_member.id)
        self.assertEqual(donation.payment_method, "mobile_money")
        self.assertEqual(donation.amount_cash, Decimal("100"))

        # Polling again after it's cleared must never create a second GiftDonation.
        with mock.patch("payments.services.PaystackMomoProvider", return_value=PaystackMomoProvider(http_get=mock_get)):
            payment_services.check_and_finalize_momo_payment(finalized)
        self.assertEqual(GiftDonation.objects.filter(funeral_event=self.funeral).count(), 1)

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_fake")
    def test_gift_momo_request_without_a_receiver_is_a_general_gift_to_the_family(self):
        mock_post = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"data": {"status": "pay_offline"}}))
        with mock.patch("payments.services.PaystackMomoProvider", return_value=PaystackMomoProvider(http_post=mock_post)):
            momo_request = payment_services.initiate_momo_gift_payment(
                funeral=self.funeral, phone_number="+233200000000", amount=Decimal("20"), donor_name="Anonymous Guest",
            )

        mock_get = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"data": {"status": "success"}}))
        with mock.patch("payments.services.PaystackMomoProvider", return_value=PaystackMomoProvider(http_get=mock_get)):
            payment_services.check_and_finalize_momo_payment(momo_request)

        donation = GiftDonation.objects.get(funeral_event=self.funeral, donor_name="Anonymous Guest")
        self.assertIsNone(donation.received_by_member)
        self.assertEqual(donation.recipient_family_id, self.asona.id)


class PaystackWebhookHttpTests(TestCase):
    """The primary, real-time path — genuinely usable now that this platform has a real, public Railway URL."""

    def setUp(self):
        self.bodi = Community.objects.create(
            name="Bodi Anidasoɔ", slug="bodi-webhook",
            default_general_male_amount=Decimal("5"), default_general_female_amount=Decimal("3"),
        )
        self.admin = User.objects.create_user(username="webhook_admin", password="x", community=self.bodi, role=Role.COMMUNITY_ADMIN)
        self.asona = family_services.create_family(community=self.bodi, name="Asona", actor=self.admin)
        family_services.recommend_family_rate(family=self.asona, amount=Decimal("50"), actor=self.admin)
        family_services.approve_family_rate(family=self.asona, actor=self.admin)
        self.member = member_services.register_member(community=self.bodi, full_name="Webhook Member", gender="male", family=self.asona)
        self.funeral = funeral_services.create_funeral_event(
            community=self.bodi, deceased_name="Webhook Deceased", deceased_gender="male",
            deceased_family=self.asona, date_of_death="2026-07-01", collection_start_date="2026-07-01",
        )
        from funerals.models import ContributionObligation
        self.obligation = ContributionObligation.objects.get(funeral_event=self.funeral, member=self.member)
        self.momo_request = MomoPaymentRequest.objects.create(
            community=self.bodi, target_type=MomoPaymentRequest.TargetType.CONTRIBUTION,
            obligation=self.obligation, phone_number="+233200000000", amount=Decimal("50"),
        )

    def _post_webhook(self, payload: dict, secret_key: str = "sk_test_fake"):
        body = json.dumps(payload).encode()
        signature = hmac.new(secret_key.encode(), body, hashlib.sha512).hexdigest()
        client = APIClient()
        return client.post("/api/payments/paystack/webhook/", data=body, content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE=signature)

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_fake")
    def test_an_unsigned_or_wrongly_signed_webhook_is_rejected(self):
        client = APIClient()
        res = client.post(
            "/api/payments/paystack/webhook/",
            data=json.dumps({"event": "charge.success", "data": {"reference": str(self.momo_request.reference_id)}}).encode(),
            content_type="application/json", HTTP_X_PAYSTACK_SIGNATURE="not-a-real-signature",
        )
        self.assertEqual(res.status_code, 401)
        self.momo_request.refresh_from_db()
        self.assertEqual(self.momo_request.status, MomoPaymentRequest.Status.PENDING)

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_fake")
    def test_a_correctly_signed_charge_success_webhook_finalizes_the_payment(self):
        with mock.patch("payments.services.PaystackMomoProvider") as MockProvider:
            MockProvider.return_value.check_status.return_value = "SUCCESSFUL"
            res = self._post_webhook({"event": "charge.success", "data": {"reference": str(self.momo_request.reference_id)}})
        self.assertEqual(res.status_code, 200)
        self.momo_request.refresh_from_db()
        self.assertEqual(self.momo_request.status, MomoPaymentRequest.Status.SUCCESSFUL)
        self.obligation.refresh_from_db()
        self.assertEqual(self.obligation.amount_paid, Decimal("50"))

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_fake")
    def test_a_correctly_signed_charge_failed_webhook_marks_it_failed(self):
        res = self._post_webhook({"event": "charge.failed", "data": {"reference": str(self.momo_request.reference_id)}})
        self.assertEqual(res.status_code, 200)
        self.momo_request.refresh_from_db()
        self.assertEqual(self.momo_request.status, MomoPaymentRequest.Status.FAILED)

    @override_settings(PAYSTACK_SECRET_KEY="sk_test_fake")
    def test_a_webhook_for_a_reference_that_doesnt_exist_is_a_harmless_no_op(self):
        res = self._post_webhook({"event": "charge.success", "data": {"reference": "not-a-real-reference"}})
        self.assertEqual(res.status_code, 200)
