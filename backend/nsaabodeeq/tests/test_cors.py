"""
'Failed to fetch' in a real browser, on every single API call — the
actual bug was django-cors-headers never being installed or configured
at all, even though the frontend (localhost:3000) and backend
(localhost:8000) are different origins as far as a browser is
concerned.

Worth being precise about why 363+ existing tests never caught this:
NOT because it was fundamentally untestable — Django's test client
genuinely does route requests through the full middleware stack,
CorsMiddleware included, exactly like a real request would be. It's
that none of those tests ever set an Origin header or asserted
anything about CORS response headers, because CORS hadn't been treated
as its own testable concern until a real browser surfaced it. These
tests exist so that gap can't reopen silently.
"""

from django.test import TestCase


class CorsConfigurationTests(TestCase):
    def test_an_allowed_frontend_origin_gets_the_cors_header(self):
        response = self.client.options(
            "/api/auth/login/",
            HTTP_ORIGIN="http://localhost:3000",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://localhost:3000")

    def test_the_allow_headers_list_includes_authorization(self):
        """The frontend sends its JWT as an Authorization header on every request — without this, login itself would work but every subsequent authenticated call would fail the same way."""
        response = self.client.options(
            "/api/auth/login/",
            HTTP_ORIGIN="http://localhost:3000",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization",
        )
        self.assertIn("authorization", response["Access-Control-Allow-Headers"].lower())

    def test_an_untrusted_origin_does_not_get_the_cors_header(self):
        """Confirms this is a real allowlist, not an 'allow everything' misconfiguration that would be its own security problem."""
        response = self.client.options(
            "/api/auth/login/",
            HTTP_ORIGIN="http://evil-site.example.com",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
        )
        self.assertNotIn("Access-Control-Allow-Origin", response)

    def test_the_actual_response_carries_the_header_not_just_the_preflight(self):
        """Browsers enforce CORS on the real response too, not only the OPTIONS preflight — a real login POST must carry the header just as much as the preflight does."""
        response = self.client.post(
            "/api/auth/login/",
            data={"username": "does-not-exist", "password": "wrong"},
            content_type="application/json",
            HTTP_ORIGIN="http://localhost:3000",
        )
        self.assertEqual(response["Access-Control-Allow-Origin"], "http://localhost:3000")
