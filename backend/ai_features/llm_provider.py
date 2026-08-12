"""
Meeting summarization — the one item on the master brief's AI list that
genuinely needs a real language model call, not a statistic or a rule.
Written against Anthropic's Messages API
(https://docs.anthropic.com/en/api/messages), which — unlike Twilio,
WhatsApp, or MTN MoMo elsewhere in this platform — I have unusually high
confidence in the exact shape of, since it's the same API this
assistant itself is built on. Even so, this sandbox has no
ANTHROPIC_API_KEY configured and no network route to api.anthropic.com,
so it's tested the same honest way as those other providers: mocking
the HTTP call and asserting the request is built correctly, never
actually invoked against a live account here.
"""

from django.conf import settings


class ProviderNotConfiguredError(Exception):
    pass


class LlmProviderError(Exception):
    pass


SUMMARY_SYSTEM_PROMPT = (
    "You summarize community funeral-society meeting transcripts into concise minutes. "
    "Respond ONLY with JSON: {\"summary\": string, \"decisions\": [string], \"action_items\": [string]}. "
    "No markdown, no commentary outside the JSON."
)

# 'Add AI features to make it greater' — a genuinely new, domain-fitting
# capability, distinct from the chatbot/summarizer/prediction features
# already built. A grieving family often struggles to put a lifetime
# into words at the hardest possible time; this drafts a real starting
# point from whatever details they can give, in their own words about
# their own person — never invented, never automatically published
# (the family still reviews and edits before it goes on the public
# memorial page, the same "opt-in, never automatic" principle that
# page already follows for everything else on it).
TRIBUTE_DRAFT_SYSTEM_PROMPT = """You write warm, dignified funeral tribute drafts for a Ghanaian community funeral and welfare platform's public memorial page.

You will be given the deceased's name, and a few details the family has provided in their own words (things like their character, what they loved, their work, their family, memorable qualities). Write a short, respectful tribute (120-200 words) that a grieving family could use as a genuine starting point — warm and personal, never generic or clinical, never morbid.

Critical: use ONLY the details actually given to you. Never invent specific facts (occupations, family details, achievements, dates) that weren't provided — if very little was given, write something shorter and more general rather than fabricating specifics. This is explicitly a draft for the family to review and edit themselves, not a finished, final text.

Respond with the tribute text only — no title, no markdown, no commentary before or after it."""


class TributeDraftProvider:
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, http_post=None):
        import requests
        self._http_post = http_post or requests.post

    def draft(self, *, deceased_name: str, key_details: str) -> str:
        api_key = getattr(settings, "ANTHROPIC_API_KEY", None)
        if not api_key:
            raise ProviderNotConfiguredError(
                "Tribute drafting isn't configured — set ANTHROPIC_API_KEY to enable it."
            )
        if not key_details.strip():
            raise LlmProviderError("Please share at least a few details about your loved one to draft from.")

        user_message = f"Deceased's name: {deceased_name}\n\nDetails from the family:\n{key_details.strip()}"
        response = self._http_post(
            self.API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-5"),
                "max_tokens": 512,
                "system": TRIBUTE_DRAFT_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_message}],
            },
            timeout=30,
        )
        if response.status_code >= 400:
            raise LlmProviderError(f"Anthropic API returned {response.status_code}: {response.text}")

        body = response.json()
        return body["content"][0]["text"].strip()

# "Add chatbot to all user types." Deliberately scoped as a HELP
# assistant, not a data-querying agent: it knows how the platform
# works and what each role can do, but never has access to anyone's
# actual balances, payments, or records, and is explicitly instructed
# never to invent a specific figure — the same restraint this whole
# platform already applies to itself around fabricated numbers.
CHATBOT_SYSTEM_PROMPT = """You are the help assistant built into Nsaabodeɛ Smart, a Ghanaian community funeral and welfare management platform. You are talking to a real, signed-in user of the app — {role_label}, in the community "{community_name}".

Your job: help them understand HOW to use the platform, explain what a feature does, and point them to the right page. You do NOT have access to their financial records, balances, or anyone else's data, and you must NEVER invent a specific number (an amount owed, collected, or any total) — if asked for one, tell them exactly which real page shows it (e.g. "My Receipts" for their own payment history, "Reports" for community totals, "Notifications" for delivery status) rather than guessing at a figure.

What's actually built in this platform, so you never describe a feature that doesn't exist:
- Four separate ledgers per funeral: Family (the deceased's own family), Community (general members), Town Leaders (chiefs/elders), and Guest (visiting well-wishers) — tracked separately, never mixed.
- A Family Head requests a funeral opening; two of {{Chairman, Secretary, Community Admin}} must approve before any member is billed.
- Payments record as cash, Mobile Money, or bank at Front Desk, by a Collector or someone specifically assigned to that funeral's desk.
- A payment recorded in error can be corrected: an authorized officer requests a reversal, a different authorized officer approves it — never a unilateral edit.
- Gift donations are separate from mandatory contributions, and stay visible only to the family and community admin.
- Tasks can be assigned by Community Admin, Chairman, Secretary (to anyone in the community) or a Family Head (only to their own family's members).
- A Notice Board carries community announcements, reviewed by a Platform Administrator before they go live.

Keep answers short, warm, and practical — a sentence or two unless more detail is genuinely asked for. If a question is really about their own personal data, say so plainly and name the real page to check, rather than answering as if you know the number."""


class ChatbotProvider:
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, http_post=None):
        import requests
        self._http_post = http_post or requests.post

    def reply(self, *, role_label: str, community_name: str, history: list) -> str:
        """
        `history` is a list of {"role": "user"|"assistant", "content": str}
        dicts, oldest first — the same shape the Anthropic Messages API
        itself expects, so no translation layer is needed between what
        gets persisted and what gets sent.
        """
        api_key = getattr(settings, "ANTHROPIC_API_KEY", None)
        if not api_key:
            raise ProviderNotConfiguredError(
                "The chatbot isn't configured — set ANTHROPIC_API_KEY to enable it."
            )
        if not history:
            raise LlmProviderError("Cannot reply to an empty conversation.")

        system_prompt = CHATBOT_SYSTEM_PROMPT.format(role_label=role_label, community_name=community_name or "none yet")
        response = self._http_post(
            self.API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-5"),
                "max_tokens": 512,
                "system": system_prompt,
                "messages": history,
            },
            timeout=30,
        )
        if response.status_code >= 400:
            raise LlmProviderError(f"Anthropic API returned {response.status_code}: {response.text}")

        body = response.json()
        return body["content"][0]["text"]


class MeetingSummaryProvider:
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, http_post=None):
        import requests
        self._http_post = http_post or requests.post

    def summarize(self, transcript: str) -> dict:
        api_key = getattr(settings, "ANTHROPIC_API_KEY", None)
        if not api_key:
            raise ProviderNotConfiguredError(
                "Meeting summarization isn't configured — set ANTHROPIC_API_KEY to enable it."
            )
        if not transcript.strip():
            raise LlmProviderError("Cannot summarize an empty transcript.")

        response = self._http_post(
            self.API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-5"),
                "max_tokens": 1024,
                "system": SUMMARY_SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": transcript}],
            },
            timeout=30,
        )
        if response.status_code >= 400:
            raise LlmProviderError(f"Anthropic API returned {response.status_code}: {response.text}")

        import json
        body = response.json()
        text = body["content"][0]["text"]
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise LlmProviderError(f"Model did not return valid JSON: {text[:200]}") from exc
