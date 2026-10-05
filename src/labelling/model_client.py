"""Jev (System One / Decisions API) enrichment client.

OpenCode-owned implementation of the ``ModelClient`` protocol drafted in PREP.md and
docs/INTERFACES.md. One HTTP request classifies up to ``MAX_BATCH`` reviews: the shared rubric and
the batch's review texts go in ``state``; each review gets five named questions
(``topic_<id>``, ``intent_<id>``, ``severity_<id>``, ``sentiment_<id>``, ``needs_review_<id>``).
Answers come back keyed per review, which lets us validate every returned ID.

Provider options:
- TypeSafe (default): Jev direct from its maker, `https://api.typesafe.ai/v1/systemone`, model
  `jev-latest` (official docs). Reads TYPESAFE_API_KEY. Same state+questions schema.
- OpenRouter: `typesafe/jev-1.13` (Jev) or any OpenRouter decisions model
  (`inception/mercury-decide:free`, etc.) via `https://openrouter.ai/api/alpha/decisions`.
  Needs only an OpenRouter API key (no TypeSafe account, no paid base subscription).
- BeatAPI: Jev via BeatAPI's reseller endpoint (`api.beatapi.io/v1/systemone`).

Real calls require ``TYPESAFE_API_KEY`` (or ``OPENROUTER_API_KEY`` / ``BEATAPI_API_KEY``) and cost nothing on a free
decisions model. No paid call is ever made at import time; ``create_client`` returns the mock
when no key is configured.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence

from . import prompts
from .extract import extract_entities, extract_evidence_quote

DEFAULT_ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
BEATAPI_ENDPOINT = "https://api.beatapi.io/v1/systemone"
TYPESAFE_ENDPOINT = "https://api.typesafe.ai/v1/systemone"
TYPESAFE_MODEL = "jev-1.13.0"  # pinned: served version reported by the first live call (Oct 5 2026)
FREE_MODEL = "typesafe/jev-1.13"
PAID_MODEL = "typesafe/jev-1.13"
MAX_BATCH = 50
CONTEXT_LIMIT = 32000

# OpenRouter hostable "decisions" models using the same state+questions schema as Jev.
OPENROUTER_MODELS = {
    "jev": "typesafe/jev-1.13",
    "jev-latest": "~typesafe/jev-latest",
    "mercury-decide-free": "inception/mercury-decide:free",
    "pplx-decider-v1-27b": "perplexity/pplx-decider-v1-27b",
    "liquid-d1": "liquid/d1",
}

TOPICS = ("access", "usability", "playback", "downloads", "catalog", "billing", "support", "other")
INTENTS = ("complaint", "request", "praise", "cancellation", "unclear")


class ModelClientError(Exception):
    """Base error; carries whether the failure is retryable."""

    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


class TransientModelError(ModelClientError):
    """Retryable: rate limit, timeout, 5xx, network. Harness applies bounded retries."""

    def __init__(self, message):
        super().__init__(message, retryable=True)


class InvalidModelOutput(ModelClientError):
    """Non-retryable structural failure: bad request, auth, malformed/missing answers."""

    def __init__(self, message):
        super().__init__(message, retryable=False)


@dataclass(frozen=True)
class ReviewInput:
    review_id: str
    review_text: str


@dataclass(frozen=True)
class Record:
    review_id: str
    topic: str
    intent: str
    sentiment: float
    severity: int
    entities: list = field(default_factory=list)
    evidence_quote: str = ""
    needs_review: bool = False
    label_config: str = ""


@dataclass(frozen=True)
class CallUsage:
    model: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class BatchResult:
    request_id: str
    records: Sequence[Record]
    usage: CallUsage


class ModelClient(Protocol):
    def classify_batch(self, reviews: Sequence[ReviewInput], label_config: str) -> BatchResult:
        ...


class MockClient:
    """Deterministic offline client: canned labels, zero usage, no keys. For dry-run/tests."""

    def __init__(self, model=FREE_MODEL):
        self.model = model

    def classify_batch(self, reviews, label_config):
        records = []
        for r in reviews:
            digest = hashlib.sha256(r.review_id.encode("utf-8")).hexdigest()
            topic = TOPICS[int(digest, 16) % len(TOPICS)]
            intent = INTENTS[int(digest, 16) % len(INTENTS)]
            entities = extract_entities(r.review_text)
            records.append(Record(
                review_id=r.review_id,
                topic=topic,
                intent=intent,
                sentiment=round(((int(digest, 16) % 21) - 10) / 10, 2),
                severity=(int(digest, 16) % 5) + 1,
                entities=entities,
                evidence_quote=extract_evidence_quote(r.review_text, entities) or r.review_text,
                needs_review=bool(int(digest, 16) % 7 == 0),
                label_config=label_config,
            ))
        return BatchResult(
            request_id="mock-" + uuid.uuid4().hex,
            records=records,
            usage=CallUsage(model=self.model, input_tokens=0, output_tokens=0),
        )


class JevClient:
    """Real client for the BeatAPI Decisions API (JEV). Standard library HTTP only."""

    def __init__(self, model=FREE_MODEL, endpoint=DEFAULT_ENDPOINT, api_key=None,
                 timeout=60, needs_review_threshold=0.5):
        self.model = model
        self.endpoint = endpoint
        self.api_key = api_key or os.environ.get("BEATAPI_API_KEY", "")
        self.timeout = timeout
        self.needs_review_threshold = needs_review_threshold

    def classify_batch(self, reviews, label_config):
        if not 1 <= len(reviews) <= MAX_BATCH:
            raise InvalidModelOutput(f"batch size {len(reviews)} outside 1..{MAX_BATCH}")
        if not self.api_key:
            raise InvalidModelOutput("no BEATAPI_API_KEY configured for real JevClient")
        if len({r.review_id for r in reviews}) != len(reviews):
            raise InvalidModelOutput("duplicate review_id in batch")

        payload = {
            "model": self.model,
            "state": {
                "rubric": prompts.RUBRIC,
                "reviews": {r.review_id: r.review_text for r in reviews},
            },
            "questions": {},
        }
        for r in reviews:
            payload["questions"].update(prompts.build_questions(r.review_id))

        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint, data=body, method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            code = e.code
            detail = e.read().decode("utf-8", "replace")[:300]
            if code in (400, 401, 402, 403, 404, 422):
                raise InvalidModelOutput(f"HTTP {code}: {detail}")
            raise TransientModelError(f"HTTP {code}: {detail}")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise TransientModelError(str(e))
        except json.JSONDecodeError as e:
            raise InvalidModelOutput(f"non-JSON response: {e}")

        answers = data.get("answers")
        if not isinstance(answers, dict):
            raise InvalidModelOutput("response missing 'answers' object")
        usage = data.get("usage") or {}

        records = []
        for r in reviews:
            rid = r.review_id
            topic = self._answer_choice(answers, rid, "topic", TOPICS)
            intent = self._answer_choice(answers, rid, "intent", INTENTS)
            severity = self._answer_score_int(answers, rid, "severity", 5, low=1)
            sentiment = self._answer_score_float(answers, rid, "sentiment", len(prompts.SENTIMENT_SCALE), low=-1, high=1)
            needs_review = self._answer_noul(answers, rid, "needs_review")
            entities = extract_entities(r.review_text)
            records.append(Record(
                review_id=rid,
                topic=topic,
                intent=intent,
                sentiment=sentiment,
                severity=severity,
                entities=entities,
                evidence_quote=extract_evidence_quote(r.review_text, entities) or r.review_text,
                needs_review=needs_review,
                label_config=label_config,
            ))

        return BatchResult(
            request_id=str(data.get("id") or "req-" + uuid.uuid4().hex),
            records=records,
            usage=CallUsage(
                # Record the served version (e.g. "jev-1.13.0") when the provider reports it, so
                # calls.jsonl names the exact model that answered rather than the alias.
                model=str(data.get("model") or self.model),
                input_tokens=int(usage.get("input_tokens", 0) or 0),
                output_tokens=int(usage.get("output_tokens", 0) or 0),
            ),
        )

    @staticmethod
    def _answer(data, rid, name):
        key = f"{name}_{rid}"
        value = data.get(key)
        if not isinstance(value, dict):
            raise InvalidModelOutput(f"missing answer '{key}'")
        return value

    def _answer_choice(self, data, rid, name, allowed):
        value = self._answer(data, rid, name)
        choice = value.get("choice")
        if choice not in allowed:
            raise InvalidModelOutput(f"'{name}' for {rid}: unexpected choice {choice!r}")
        return choice

    def _answer_score_int(self, data, rid, name, buckets, low):
        value = self._answer(data, rid, name)
        score = value.get("score")
        if not isinstance(score, (int, float)):
            raise InvalidModelOutput(f"'{name}' for {rid}: non-numeric score {score!r}")
        return max(low, min(low + buckets - 1, low + round(score)))

    def _answer_score_float(self, data, rid, name, buckets, low, high):
        value = self._answer(data, rid, name)
        score = value.get("score")
        if not isinstance(score, (int, float)):
            raise InvalidModelOutput(f"'{name}' for {rid}: non-numeric score {score!r}")
        fraction = max(0.0, min(1.0, score / max(1, buckets - 1)))
        return round(low + fraction * (high - low), 2)

    def _answer_noul(self, data, rid, name):
        value = self._answer(data, rid, name)
        noul = value.get("noul")
        if not isinstance(noul, (int, float)):
            raise InvalidModelOutput(f"'{name}' for {rid}: non-numeric noul {noul!r}")
        return noul >= self.needs_review_threshold


def create_client(config=None):
    """Factory. Real JevClient when a key is configured; else MockClient (offline-safe).

    config keys: provider (default "typesafe"), model, endpoint, api_key, timeout,
    needs_review_threshold.

    Providers:
    - "typesafe" (default): Jev direct from TypeSafe (`api.typesafe.ai/v1/systemone`). Reads
      TYPESAFE_API_KEY.
    - "openrouter": Jev (`typesafe/jev-1.13` or `~typesafe/jev-latest`) or any
      OpenRouter decisions model, via `https://openrouter.ai/api/alpha/decisions`. Needs only an
      OpenRouter API key (no paid base subscription, no TypeSafe account). Reads OPENROUTER_API_KEY.
    - "beatapi": Jev via BeatAPI's Decisions reseller endpoint. Reads BEATAPI_API_KEY.
    """
    config = config or {}
    provider = config.get("provider", "typesafe").lower()
    if provider == "typesafe":
        model = config.get("model") or TYPESAFE_MODEL
        endpoint = config.get("endpoint", TYPESAFE_ENDPOINT)
        key = config.get("api_key") or os.environ.get("TYPESAFE_API_KEY", "")
    elif provider == "openrouter":
        model = config.get("model") or OPENROUTER_MODELS.get(config.get("model_alias", "jev"), FREE_MODEL)
        endpoint = config.get("endpoint", "https://openrouter.ai/api/alpha/decisions")
        key = config.get("api_key") or os.environ.get("OPENROUTER_API_KEY", "")
    elif provider == "beatapi":
        model = config.get("model") or FREE_MODEL
        endpoint = config.get("endpoint", BEATAPI_ENDPOINT)
        key = config.get("api_key") or os.environ.get("BEATAPI_API_KEY", "")
    else:
        raise InvalidModelOutput(f"unsupported provider {provider!r}")
    if not key:
        return MockClient(model=model)
    return JevClient(
        model=model,
        endpoint=endpoint,
        api_key=key,
        timeout=int(config.get("timeout", 60)),
        needs_review_threshold=float(config.get("needs_review_threshold", 0.5)),
    )


def estimate_request_tokens(reviews):
    """Cheap heuristic token estimate for the built payload, to size batches within CONTEXT_LIMIT."""
    payload = {
        "state": {
            "rubric": prompts.RUBRIC,
            "reviews": {r.review_id: r.review_text for r in reviews},
        },
        "questions": {},
    }
    for r in reviews:
        payload["questions"].update(prompts.build_questions(r.review_id))
    return len(json.dumps(payload)) // 3


def max_batch_by_tokens(review_texts, budget=CONTEXT_LIMIT, hard_cap=MAX_BATCH):
    """Largest batch whose estimated request stays within ``budget`` (default the 32k context).

    Uses a single-per-review token delta so the harness can size batches without re-encoding the
    whole payload repeatedly. ``hard_cap`` is the grading contract's 50-review request ceiling.
    """
    if not review_texts:
        return 0
    probe = [ReviewInput(f"p{i}", t) for i, t in enumerate(review_texts[:hard_cap])]
    per_review = (estimate_request_tokens(probe) - estimate_request_tokens(probe[:1])) / max(1, len(probe) - 1)
    fixed = estimate_request_tokens(probe[:1])
    budget -= fixed
    n = int(budget // max(1.0, per_review)) if per_review > 0 else hard_cap
    return max(1, min(hard_cap, n))