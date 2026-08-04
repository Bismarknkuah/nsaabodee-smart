"""
'Add chatbot to all user types.' Tested the same honest way as
meeting summarization elsewhere in this platform — this sandbox has no
ANTHROPIC_API_KEY and no network route to api.anthropic.com, so the
HTTP call is mocked and the request/response shape is asserted; never
invoked against a live account here.
"""
import unittest.mock as mock
from unittest.mock import MagicMock

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import Role, User
from ai_features import services
from ai_features.llm_provider import ChatbotProvider, ProviderNotConfiguredError
from ai_features.models import ChatbotMessage
from tenants.models import Community


class ChatbotProviderTests(TestCase):
    def test_raises_when_not_configured(self):
        with self.assertRaises(ProviderNotConfiguredError):
            ChatbotProvider().reply(role_label="Collector", community_name="Bodi", history=[{"role": "user", "content": "hi"}])

    @override_settings(ANTHROPIC_API_KEY="test-key")
    def test_a_real_looking_response_is_returned_as_plain_text(self):
        mock_post = MagicMock(return_value=MagicMock(
            status_code=200,
            json=lambda: {"content": [{"text": "You can record a payment at Front Desk."}]},
        ))
        provider = ChatbotProvider(http_post=mock_post)
        reply = provider.reply(role_label="Collector", community_name="Bodi", history=[{"role": "user", "content": "How do I record a payment?"}])
        self.assertIn("Front Desk", reply)

    @override_settings(ANTHROPIC_API_KEY="test-key")
    def test_the_system_prompt_includes_the_actual_role_and_community(self):
        """The prompt genuinely reflects who's asking — not a generic, context-free assistant."""
        mock_post = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"content": [{"text": "ok"}]}))
        provider = ChatbotProvider(http_post=mock_post)
        provider.reply(role_label="Family Head", community_name="Bodi Anidasoɔ", history=[{"role": "user", "content": "hi"}])
        sent_system_prompt = mock_post.call_args.kwargs["json"]["system"]
        self.assertIn("Family Head", sent_system_prompt)
        self.assertIn("Bodi Anidasoɔ", sent_system_prompt)

    @override_settings(ANTHROPIC_API_KEY="test-key")
    def test_the_system_prompt_explicitly_forbids_inventing_financial_figures(self):
        """The actual safety guardrail — checked directly, not assumed from the docstring."""
        mock_post = MagicMock(return_value=MagicMock(status_code=200, json=lambda: {"content": [{"text": "ok"}]}))
        provider = ChatbotProvider(http_post=mock_post)
        provider.reply(role_label="Collector", community_name="Bodi", history=[{"role": "user", "content": "hi"}])
        sent_system_prompt = mock_post.call_args.kwargs["json"]["system"]
        self.assertIn("NEVER invent a specific number", sent_system_prompt)


class AskChatbotServiceTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-chatbot")
        self.user = User.objects.create_user(username="chatbot_user", password="x", community=self.bodi, role=Role.COLLECTOR)

    def test_a_short_empty_message_is_rejected(self):
        with self.assertRaises(ValidationError):
            services.ask_chatbot(user=self.user, message="   ")

    def test_the_users_own_message_is_persisted_even_if_the_provider_fails(self):
        """'Make sure proper records are being taken' — the attempt itself is a real record, distinguishable from never having tried at all."""
        with self.assertRaises(ValidationError):
            services.ask_chatbot(user=self.user, message="How do I record a payment?")
        self.assertEqual(ChatbotMessage.objects.filter(user=self.user, role="user").count(), 1)
        self.assertEqual(ChatbotMessage.objects.filter(user=self.user, role="assistant").count(), 0)

    def test_a_successful_exchange_persists_both_the_question_and_the_reply(self):
        with mock.patch("ai_features.llm_provider.ChatbotProvider") as MockProvider:
            MockProvider.return_value.reply.return_value = "Check the Front Desk page to record a payment."
            reply = services.ask_chatbot(user=self.user, message="How do I record a payment?")

        self.assertEqual(reply.role, "assistant")
        self.assertIn("Front Desk", reply.content)
        history = services.list_chatbot_history(user=self.user)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].role, "user")
        self.assertEqual(history[1].role, "assistant")

    def test_conversation_history_is_scoped_only_to_the_asking_user(self):
        other_user = User.objects.create_user(username="chatbot_other_user", password="x", community=self.bodi, role=Role.COLLECTOR)
        with mock.patch("ai_features.llm_provider.ChatbotProvider") as MockProvider:
            MockProvider.return_value.reply.return_value = "Reply for user one."
            services.ask_chatbot(user=self.user, message="Question from user one")

        self.assertEqual(len(services.list_chatbot_history(user=other_user)), 0)
        self.assertEqual(len(services.list_chatbot_history(user=self.user)), 2)


class ChatbotHttpTests(TestCase):
    def setUp(self):
        self.bodi = Community.objects.create(name="Bodi Anidasoɔ", slug="bodi-chatbot-http")
        # Every role reaches the same endpoint — Family Head chosen arbitrarily to prove it's not role-gated.
        self.user = User.objects.create_user(username="chatbot_http_user", password="a-real-password-123", community=self.bodi, role=Role.FAMILY_HEAD)

    def _login(self):
        client = APIClient()
        login = client.post("/api/auth/login/", {"username": "chatbot_http_user", "password": "a-real-password-123"})
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        return client

    def test_the_endpoint_requires_login(self):
        client = APIClient()
        res = client.post("/api/ai/chatbot/", {"message": "hi"})
        self.assertEqual(res.status_code, 401)

    def test_a_genuine_provider_failure_returns_503_not_a_generic_500(self):
        client = self._login()
        res = client.post("/api/ai/chatbot/", {"message": "How do I request a funeral opening?"})
        self.assertEqual(res.status_code, 503)

    def test_full_round_trip_via_http(self):
        client = self._login()
        with mock.patch("ai_features.llm_provider.ChatbotProvider") as MockProvider:
            MockProvider.return_value.reply.return_value = "A Family Head can request a funeral opening from the Funerals page."
            res = client.post("/api/ai/chatbot/", {"message": "How do I request a funeral opening?"})
        self.assertEqual(res.status_code, 201)
        self.assertIn("Funerals page", res.data["content"])

        history_res = client.get("/api/ai/chatbot/history/")
        self.assertEqual(history_res.status_code, 200)
        self.assertEqual(len(history_res.data), 2)
