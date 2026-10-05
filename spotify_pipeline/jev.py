"""Jev label adapter. This module never reads golden answers or source files.

The HTTP transport is deliberately separate from request construction and
response validation. No command in this repository calls it automatically.
"""

import json
import math
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .contract import INTENTS, TOPICS
from .errors import ValidationError

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODELS_ENDPOINT = "https://api.typesafe.ai/v1/models"
MODEL = "jev-1.13.0"
PROMPT_VERSION = "jev-rubric-v2"
SCHEMA_VERSION = "jev-labels-v1"
MIN_CONFIDENCE = 0.60
MAX_ATTEMPTS = 2

TOPIC_CRITERIA = {
    "access": "Login, signup, passwords, or account access.",
    "usability": "Navigation, layout, controls, queue or playlist management, or ad interruptions.",
    "playback": "Playing, pausing, skipping, shuffling, crashes, loading failures, lag, audio or connection failures, or resource use.",
    "downloads": "Downloading music, saved downloads, offline listening, or disappearing downloads.",
    "catalog": "Missing music, artists, or podcasts; search, discovery, recommendations, or lyrics availability, including missing offline lyrics.",
    "billing": "Prices, charges, subscriptions, paywalls, premium entitlement, or explicitly premium-only controls. A paid-plan mention alone is not billing.",
    "support": "Contact with customer service or its response, not support meaning endorsement of a cause.",
    "other": "General praise or criticism, unrelated or unclear text, or no supported specific product topic. Generic 'great music app' praise is other.",
}
INTENT_CRITERIA = {
    "cancellation": "Explicitly expresses intent to leave, cancel, or stop using the service.",
    "complaint": "Reports a problem or expresses dissatisfaction without explicit cancellation intent.",
    "request": "Asks for a feature, change, or help without a clear complaint or cancellation intent.",
    "praise": "Expresses approval or satisfaction without a clear complaint or request.",
    "unclear": "Intent cannot be determined from the text.",
}
SEVERITY_CRITERIA = {
    "1": "No reported problem: praise, unclear or neutral content, or a pure feature request.",
    "2": "Minor annoyance, dislike, or general criticism without supported functional loss.",
    "3": "A function is degraded or restricted, but some use or a workaround remains.",
    "4": "A core task is clearly blocked.",
    "5": "Explicit serious financial, privacy, or data harm is reported.",
}
SENTIMENT_LEVELS = [
    "Very negative tone.",
    "Negative tone.",
    "Neutral or balanced tone.",
    "Positive tone.",
    "Very positive tone.",
]


def label_config() -> Dict[str, str]:
    return {"model": MODEL, "effort": "systemone", "prompt_version": PROMPT_VERSION,
            "schema_version": SCHEMA_VERSION}


def build_request(review_text: str) -> Dict[str, Any]:
    """One review per call. Ratings, IDs, and human answers never enter state."""
    if not isinstance(review_text, str) or not review_text.strip():
        raise ValidationError("Jev requires nonempty review text")
    return {
        "state": review_text,
        "model": MODEL,
        "questions": {
            "topic": {"type": "choice", "instructions": (
                "Choose only a product topic supported by the review text. For multiple problems, "
                "choose the highest supported severity; on a tie, choose the first specific problem mentioned. "
                "For a positive review, choose the first specific praised feature; general praise is other. "
                "A Premium mention alone is not billing; an explicitly premium-only control is billing. "
                "Ad interruptions are usability, loading failures are playback, and missing offline lyrics are catalog."
            ), "criteria": TOPIC_CRITERIA},
            "intent": {"type": "choice", "instructions": "Choose the reviewer's clearest expressed intent. Do not infer cancellation from low stars.", "criteria": INTENT_CRITERIA},
            "severity": {"type": "choice", "instructions": "Choose the highest reported harm or lost function supported by the words. Tone and star rating do not set harm.", "criteria": SEVERITY_CRITERIA},
            "sentiment": {"type": "score", "instructions": "Rate the tone of the review independently of functional severity.", "criteria": SENTIMENT_LEVELS},
        },
    }


def _confidence(answer: Dict[str, Any]) -> float:
    value = answer.get("confidence")
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or not 0 <= value <= 1:
        raise ValidationError("Jev answer has invalid confidence")
    return float(value)


@dataclass(frozen=True)
class JevLabels:
    topic: str
    intent: str
    severity: int
    sentiment: float
    needs_review: bool
    confidence: Dict[str, float]
    model: str
    input_tokens: int
    output_tokens: int


def parse_response(payload: Dict[str, Any], threshold: float = MIN_CONFIDENCE) -> JevLabels:
    """Reject unknown labels, malformed scores, missing usage, and model drift."""
    if not isinstance(payload, dict) or payload.get("model") != MODEL:
        raise ValidationError("Jev response model differs from pinned version")
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or not 0 <= threshold <= 1:
        raise ValidationError("invalid confidence threshold")
    answers = payload.get("answers")
    if not isinstance(answers, dict) or set(answers) != {"topic", "intent", "severity", "sentiment"}:
        raise ValidationError("Jev response question set differs from request")
    confidence = {}
    for key, kind in (("topic", "choice"), ("intent", "choice"), ("severity", "choice"), ("sentiment", "score")):
        answer = answers[key]
        if not isinstance(answer, dict) or answer.get("type") != kind:
            raise ValidationError("Jev response has invalid answer type")
        confidence[key] = _confidence(answer)
    topic = answers["topic"].get("choice")
    intent = answers["intent"].get("choice")
    severity_choice = answers["severity"].get("choice")
    if topic not in TOPICS or intent not in INTENTS or severity_choice not in SEVERITY_CRITERIA:
        raise ValidationError("Jev response has unknown choice")
    score = answers["sentiment"].get("score")
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 4:
        raise ValidationError("Jev sentiment score must be within 0..4")
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        raise ValidationError("Jev usage is missing")
    for key in ("input_tokens", "output_tokens"):
        value = usage.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValidationError("Jev usage must contain nonnegative integer token counts")
    needs_review = min(confidence.values()) < threshold or topic == "other" or intent == "unclear"
    return JevLabels(topic, intent, int(severity_choice), (float(score) - 2) / 2,
                     needs_review, confidence, MODEL,
                     usage["input_tokens"], usage["output_tokens"])


class JevHTTPError(Exception):
    def __init__(self, status: int, retry_after: Optional[float] = None):
        super().__init__("Jev HTTP status %s" % status)
        self.status = status
        self.retry_after = retry_after


def post_systemone(request_body: Dict[str, Any], api_key: str, timeout: float = 20.0) -> Dict[str, Any]:
    """Standard-library HTTP transport. Caller must enforce a paid-call budget."""
    if not api_key:
        raise ValidationError("TypeSafe API key is missing")
    body = json.dumps(request_body, ensure_ascii=False, allow_nan=False).encode("utf-8")
    request = urllib.request.Request(ENDPOINT, data=body,
                                     headers={"Authorization": "Bearer " + api_key,
                                              "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raw_after = error.headers.get("retry-after")
        try:
            retry_after = min(max(float(raw_after), 0), 30) if raw_after else None
        except ValueError:
            retry_after = None
        raise JevHTTPError(error.code, retry_after) from None


def check_model_access(api_key: str, timeout: float = 10.0) -> None:
    """Read-only account check. Versioned model IDs may not appear in listing."""
    if not api_key:
        raise ValidationError("TypeSafe API key is missing")
    request = urllib.request.Request(MODELS_ENDPOINT,
                                     headers={"Authorization": "Bearer " + api_key}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        raise JevHTTPError(error.code) from None
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list) or "jev-latest" not in [
            item.get("name") for item in models if isinstance(item, dict)]:
        raise ValidationError("TypeSafe model listing does not show jev-latest")


def enrich_labels(review_text: str, api_key: str, transport=post_systemone,
                  sleep=time.sleep) -> Dict[str, Any]:
    """Return labels and accounting only; no entity or quote extraction.

    Retry at most once for 429/5xx. Return no fabricated usage on failure.
    Timeouts are not retried because provider billing outcome may be unknown.
    """
    request = build_request(review_text)
    started = time.monotonic()
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            payload = transport(request, api_key)
            labels = parse_response(payload)
            return {"labels": labels, "attempts": attempt,
                    "elapsed_seconds": time.monotonic() - started}
        except JevHTTPError as error:
            if attempt == MAX_ATTEMPTS or error.status not in (429, 500, 502, 503, 504):
                raise
            sleep(error.retry_after if error.retry_after is not None else 1.0)
    raise RuntimeError("unreachable")


def combine_with_evidence(labels: JevLabels, review_text: str, entities: list,
                          evidence_quote: str) -> Dict[str, Any]:
    """Keep extraction separate and require exact source evidence."""
    if not isinstance(entities, list) or not all(isinstance(x, str) and x.strip() for x in entities):
        raise ValidationError("entities must be a list of nonblank strings")
    if not isinstance(evidence_quote, str) or not evidence_quote.strip() or evidence_quote not in review_text:
        raise ValidationError("evidence_quote must be a nonblank exact source substring")
    return {"topic": labels.topic, "intent": labels.intent, "severity": labels.severity,
            "sentiment": labels.sentiment, "needs_review": labels.needs_review,
            "entities": entities, "evidence_quote": evidence_quote}
