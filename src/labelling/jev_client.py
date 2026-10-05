"""BeatAPI JEV client for the enrichment role (labelling side).

JEV (BeatAPI Decisions API, POST https://api.beatapi.io/v1/systemone) answers typed
questions about a `state` -- it returns choices/probabilities/scores, NOT free text.
So this client splits the A5 record schema into:

  JEV-decided fields              how
  -----------------------------   ---------------------------------------------------
  topic                           `choice` over the 8 contract topics
  intent                          `choice` over the 5 intents (precedence in instructions)
  severity                        `score` over the 5-level scale -> round(index) + 1
  sentiment                       `score` over 5 valence levels  -> (score - 2) / 2
  needs_review                    `noul` "needs human review" OR low topic/intent confidence
  evidence_quote (multi-sentence) `choice` over the review's own sentences (always a substring)

  Code-decided fields             how
  -----------------------------   ---------------------------------------------------
  entities                        fixed feature lexicon, only terms literally present in text
  evidence_quote (single sentence) whole stripped text (exact substring by construction)

Several reviews are packed into ONE request (<= 50, contract limit): `state` is a JSON
object keyed by local ids (r01, r02, ...) and every question is namespaced `r01__topic`.

Safety: standard library only; importing this module never makes a network call; with no
BEATAPI_API_KEY in the environment `create_client` returns the dry-run client.
"""
from __future__ import annotations

import json
import os
import random
import re
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Mapping, Sequence

# --------------------------------------------------------------------------- types
# Use the shared contract from model_client.py once infra delivers it; fall back to the
# PREP.md draft so this file is usable today.
try:  # pragma: no cover
    from .model_client import (  # type: ignore
        BatchResult, CallUsage, InvalidModelOutput, ModelClientError, Record,
        ReviewInput, TransientModelError,
    )
except Exception:  # noqa: BLE001
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

    class ModelClientError(Exception): ...
    class TransientModelError(ModelClientError): ...
    class InvalidModelOutput(ModelClientError): ...

# --------------------------------------------------------------------------- config
ENDPOINT = "https://api.beatapi.io/v1/systemone"
FREE_MODEL = "jev-1.13-free"   # $0; 1 req/min before first top-up, 10/min after any top-up
PAID_MODEL = "jev-1.13"        # $0.042 / 1M input tokens, output not billed
PROVIDER = "beatapi"
PROMPT_VERSION = "jev-v1"
SCHEMA_VERSION = "a5-v1"
MAX_BATCH = 50                 # contract hard limit
CONTEXT_LIMIT_TOKENS = 32_000  # state + questions combined
DEFAULT_RPM = {FREE_MODEL: 1}  # raise to 10 after a top-up (set rpm in config)


def make_label_config(model: str, batch_size: int) -> str:
    # batch size is part of the config: packing changes what the model sees.
    return f"{PROVIDER}/{model}:prompt-{PROMPT_VERSION}:schema-{SCHEMA_VERSION}:pack{batch_size}"


# --------------------------------------------------------------------------- rubric
# Wording mirrors GRADING_CONTRACT.md as summarised in README/PREP. Golden labels never go here.
TOPICS = {
    "access": "Login, sign-up, account access, verification, being logged out or locked out.",
    "usability": "UI/UX, navigation, layout, design changes, features hard to find or use, ads experience in the app.",
    "playback": "Playing audio: stopping, skipping, crashes or freezes during play, shuffle/queue behaviour, audio quality.",
    "downloads": "Offline downloads: downloading, storage, downloaded songs disappearing or not playing offline.",
    "catalog": "Content availability: missing songs/artists/podcasts, regional availability, recommendations quality.",
    "billing": "Charges, payments, refunds, subscription price or plan changes. A mere mention of a paid plan is NOT billing.",
    "support": "Customer service, help channels, response from Spotify staff.",
    "other": "General praise or criticism with no specific problem area, or anything not covered above.",
}
INTENTS = {
    "cancellation": "Explicitly says they are leaving, uninstalling, cancelling or switching away (personal departure).",
    "complaint": "Reports a problem or criticises the product (including a general 'bad app').",
    "request": "Asks for a feature or change without a reported problem.",
    "praise": "Positive feedback without a reported problem.",
    "unclear": "Unrelated text, bare boycott slogans, or no interpretable product meaning.",
}
SEVERITY_LEVELS = [
    "1 - no reported problem: praise, unclear, or pure request",
    "2 - annoyance or generic criticism",
    "3 - degraded or restricted function, some use remaining",
    "4 - a clearly blocked core task",
    "5 - explicit serious financial, privacy or data harm",
]
SENTIMENT_LEVELS = ["very negative", "negative", "neutral or mixed", "positive", "very positive"]

# Short per-question criteria; the full definitions above travel ONCE per request in state.rubric.
TOPICS_SHORT = {"access": "login/account access", "usability": "UI, navigation, ads experience",
                "playback": "playing audio, crashes in play, shuffle/queue", "downloads": "offline downloads",
                "catalog": "missing content, recommendations", "billing": "charges, payments, price, refunds",
                "support": "customer service", "other": "general praise/criticism, none of the above"}
INTENTS_SHORT = {"cancellation": "explicit personal departure", "complaint": "reports a problem or criticises",
                 "request": "asks for a feature/change", "praise": "positive, no problem",
                 "unclear": "unrelated or uninterpretable"}
SEVERITY_SHORT = ["1 none/praise/request", "2 annoyance", "3 degraded", "4 core task blocked", "5 financial/privacy/data harm"]
SENTIMENT_SHORT = ["very negative", "negative", "neutral", "positive", "very positive"]
RUBRIC = {"topic": {"definitions": TOPICS, "rule": None}, "intent": {"definitions": INTENTS, "rule": None},
          "severity": {"levels": SEVERITY_LEVELS, "rule": None}, "needs_review": None,
          "note": "Labels must come from review text only. Star ratings are not provided."}

TOPIC_INSTR = ("Primary topic of this review text. If several problems are mentioned, choose the one with "
               "the highest supported severity; on a tie, the first specific problem mentioned. "
               "Use only the review text; star ratings are not provided and must not be assumed.")
INTENT_INSTR = ("Intent of this review text. Precedence when several apply: cancellation > complaint > "
                "request > praise > unclear. Do not infer a specific defect from general negativity.")
SEVERITY_INSTR = ("Severity of the most severe problem the text actually supports. Cancellation intent or "
                  "angry language alone does NOT raise severity. Never invent impact.")
SENTIMENT_INSTR = "Overall emotional valence of the review text."
REVIEW_INSTR = ("Should a human check these labels? True if the text is ambiguous, in a language you cannot "
                "interpret reliably, sarcastic, or lacks context needed to label it.")
QUOTE_INSTR = "Which sentence of this review best supports its topic and intent label?"

RUBRIC["topic"]["rule"] = TOPIC_INSTR
RUBRIC["intent"]["rule"] = INTENT_INSTR
RUBRIC["severity"]["rule"] = SEVERITY_INSTR
RUBRIC["needs_review"] = REVIEW_INSTR

# Explicit feature terms -> canonical entity. Only emitted when the term appears in the text.
ENTITY_LEXICON = {
    "ads": ["ad", "ads", "advert", "adverts", "advertisement", "advertisements", "commercial", "commercials"],
    "shuffle": ["shuffle"], "lyrics": ["lyrics"], "premium": ["premium"],
    "login": ["login", "log in", "sign in", "signin", "logged out", "password"],
    "podcast": ["podcast", "podcasts"], "playlist": ["playlist", "playlists"],
    "download": ["download", "downloads", "downloaded", "offline"], "queue": ["queue"],
    "skip": ["skip", "skips", "skipping"], "price": ["price", "prices", "expensive", "cost"],
    "refund": ["refund", "refunds"], "update": ["update", "updated", "updates"],
    "crash": ["crash", "crashes", "crashing"], "bluetooth": ["bluetooth"],
    "family plan": ["family plan"], "student plan": ["student"],
    "car": ["car", "android auto"], "widget": ["widget"], "dj": ["dj"],
}
_ENTITY_RX = {k: re.compile(r"\b(" + "|".join(re.escape(t) for t in v) + r")\b", re.I)
              for k, v in ENTITY_LEXICON.items()}


def extract_entities(text: str) -> list[str]:
    return [k for k, rx in _ENTITY_RX.items() if rx.search(text)]


_SENT_RX = re.compile(r"[^.!?\n]+[.!?]*")


def split_sentences(text: str) -> list[str]:
    """Exact substrings of `text` (stripped), so any choice is a valid evidence_quote."""
    out = [m.group(0).strip() for m in _SENT_RX.finditer(text)]
    return [s for s in out if s and s in text][:12]


# --------------------------------------------------------------------------- request build
def build_request(reviews: Sequence[ReviewInput], model: str) -> tuple[dict, dict]:
    """Returns (payload, local_index) where local_index maps local id -> (review, sentences)."""
    if not 1 <= len(reviews) <= MAX_BATCH:
        raise ValueError(f"batch must be 1..{MAX_BATCH}, got {len(reviews)}")
    state, questions, index = {}, {}, {}
    for i, r in enumerate(reviews, 1):
        lid = f"r{i:02d}"
        sents = split_sentences(r.review_text)
        index[lid] = (r, sents)
        state[lid] = r.review_text
        about = f"Review reviews.{lid} only, using state.rubric. "
        questions[f"{lid}__topic"] = {"type": "choice", "instructions": about + "Primary topic?", "criteria": TOPICS_SHORT}
        questions[f"{lid}__intent"] = {"type": "choice", "instructions": about + "Intent (apply precedence)?", "criteria": INTENTS_SHORT}
        questions[f"{lid}__severity"] = {"type": "score", "instructions": about + "Supported severity?", "criteria": SEVERITY_SHORT}
        questions[f"{lid}__sentiment"] = {"type": "score", "instructions": about + SENTIMENT_INSTR, "criteria": SENTIMENT_SHORT}
        questions[f"{lid}__review"] = {"type": "noul", "instructions": about + "Needs human review (see rubric)?"}
        if len(sents) > 1:
            questions[f"{lid}__quote"] = {"type": "choice", "instructions": about + QUOTE_INSTR,
                                          "criteria": {f"s{j}": s for j, s in enumerate(sents)}}
    payload = {"model": model, "state": {"rubric": RUBRIC, "reviews": state}, "questions": questions}
    approx_tokens = len(json.dumps(payload, ensure_ascii=False)) // 3  # conservative estimate
    if approx_tokens > CONTEXT_LIMIT_TOKENS:
        raise ValueError(f"~{approx_tokens} tokens > {CONTEXT_LIMIT_TOKENS}; reduce batch size")
    return payload, index


# --------------------------------------------------------------------------- response parse
def _q(answers: Mapping, key: str) -> Mapping:
    a = answers.get(key)
    if not isinstance(a, Mapping):
        raise InvalidModelOutput(f"missing answer {key}")
    return a


def parse_response(body: Mapping, index: Mapping, label_config: str,
                   review_conf_floor: float = 0.5, review_noul_ceiling: float = 0.5) -> list[Record]:
    answers = body.get("answers")
    if not isinstance(answers, Mapping):
        raise InvalidModelOutput("response has no answers object")
    records = []
    for lid, (rev, sents) in index.items():
        t, it = _q(answers, f"{lid}__topic"), _q(answers, f"{lid}__intent")
        sev, sen = _q(answers, f"{lid}__severity"), _q(answers, f"{lid}__sentiment")
        nr = _q(answers, f"{lid}__review")
        topic, intent = t.get("choice"), it.get("choice")
        if topic not in TOPICS or intent not in INTENTS:
            raise InvalidModelOutput(f"{lid}: bad topic/intent {topic!r}/{intent!r}")
        try:
            s_idx = float(sev["score"]); v_idx = float(sen["score"]); p_rev = float(nr["noul"])
        except (KeyError, TypeError, ValueError) as e:
            raise InvalidModelOutput(f"{lid}: bad score/noul ({e})") from e
        severity = int(min(5, max(1, round(s_idx) + 1)))       # exact int 1..5
        sentiment = round(min(1.0, max(-1.0, (v_idx - 2) / 2)), 4)  # finite, [-1, 1]
        low_conf = min(float(t.get("confidence", 1)), float(it.get("confidence", 1))) < review_conf_floor
        needs_review = bool(p_rev >= review_noul_ceiling or low_conf)
        quote = rev.review_text.strip()
        if len(sents) > 1:
            q = answers.get(f"{lid}__quote", {})
            ch = q.get("choice") if isinstance(q, Mapping) else None
            if isinstance(ch, str) and ch.startswith("s") and ch[1:].isdigit() and int(ch[1:]) < len(sents):
                quote = sents[int(ch[1:])]
        if not quote or quote not in rev.review_text:
            raise InvalidModelOutput(f"{lid}: evidence_quote not a substring")
        records.append(Record(review_id=rev.review_id, topic=topic, intent=intent, sentiment=sentiment,
                              severity=severity, entities=extract_entities(rev.review_text),
                              evidence_quote=quote, needs_review=needs_review, label_config=label_config))
    return records


# --------------------------------------------------------------------------- rate limit
class MinuteLimiter:
    """Simple shared spacing limiter (requests per minute). Infra's spend module may replace it."""
    def __init__(self, rpm: float):
        self.gap = 60.0 / max(rpm, 0.001)
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = max(0.0, self._next - now)
            self._next = max(now, self._next) + self.gap
        if delay:
            time.sleep(delay)


# --------------------------------------------------------------------------- clients
class JevClient:
    def __init__(self, api_key: str, model: str = FREE_MODEL, rpm: float | None = None,
                 timeout: float = 120.0, max_transient_retries: int = 4):
        self.api_key, self.model, self.timeout = api_key, model, timeout
        self.max_retries = max_transient_retries
        self.limiter = MinuteLimiter(rpm or DEFAULT_RPM.get(model, 60))

    def _post(self, payload: dict, idem_key: str) -> dict:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        for attempt in range(self.max_retries + 1):
            self.limiter.wait()
            req = urllib.request.Request(ENDPOINT, data=data, method="POST", headers={
                "Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json",
                "Idempotency-Key": idem_key})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")
                if e.code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                    ra = e.headers.get("Retry-After")
                    sleep = float(ra) if ra and ra.replace(".", "", 1).isdigit() else 2 ** attempt
                    time.sleep(sleep + random.uniform(0, 1))
                    continue
                cls = TransientModelError if e.code in (429, 500, 502, 503, 504) else ModelClientError
                raise cls(f"HTTP {e.code}: {body[:500]}") from e
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt + random.uniform(0, 1))
                    continue
                raise TransientModelError(str(e)) from e
        raise TransientModelError("retries exhausted")

    def classify_batch(self, reviews: Sequence[ReviewInput], label_config: str) -> BatchResult:
        payload, index = build_request(reviews, self.model)
        idem = str(uuid.uuid4())
        body = self._post(payload, idem)
        if body.get("model") and body["model"] != self.model:
            raise InvalidModelOutput(f"served model {body['model']!r} != requested {self.model!r}")
        records = parse_response(body, index, label_config)
        usage = body.get("usage") or {}
        return BatchResult(request_id=str(body.get("id") or idem), records=records,
                           usage=CallUsage(model=self.model,
                                           input_tokens=int(usage.get("input_tokens", 0)),
                                           output_tokens=int(usage.get("output_tokens", 0))))


class DryRunJevClient(JevClient):
    """No network. Builds the real payload, then fabricates a structurally valid response."""
    def __init__(self, model: str = FREE_MODEL):
        self.model = model
        self.last_payload: dict | None = None

    def _post(self, payload: dict, idem_key: str) -> dict:
        self.last_payload = payload
        answers = {}
        for k, q in payload["questions"].items():
            if q["type"] == "choice":
                first = next(iter(q["criteria"]))
                answers[k] = {"type": "choice", "choice": first, "probabilities": {first: 1}, "confidence": 1}
            elif q["type"] == "score":
                answers[k] = {"type": "score", "score": 1.0, "confidence": 1}
            else:
                answers[k] = {"type": "noul", "noul": 0.1}
        return {"id": f"dryrun_{idem_key}", "model": self.model, "answers": answers,
                "usage": {"input_tokens": 0, "output_tokens": 0}}


def create_client(config: Mapping) -> JevClient:
    """config keys: model, rpm, dry_run. Real client only when BEATAPI_API_KEY is set and not dry_run."""
    model = config.get("model", FREE_MODEL)
    key = os.environ.get("BEATAPI_API_KEY", "").strip()
    if config.get("dry_run") or not key:
        return DryRunJevClient(model)
    return JevClient(key, model=model, rpm=config.get("rpm"))


# --------------------------------------------------------------------------- smoke test
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="JEV smoke test (dry-run unless --live)")
    ap.add_argument("--live", action="store_true", help="make ONE real call (needs BEATAPI_API_KEY)")
    ap.add_argument("--model", default=FREE_MODEL)
    ap.add_argument("--show-payload", action="store_true")
    a = ap.parse_args()
    demo = [ReviewInput("demo-1", "Keeps logging me out every day. I can't even open my playlists."),
            ReviewInput("demo-2", "Love it! Best music app. Please bring back the old shuffle though.")]
    client = create_client({"model": a.model, "dry_run": not a.live})
    lc = make_label_config(a.model, len(demo))
    res = client.classify_batch(demo, lc)
    if a.show_payload and getattr(client, "last_payload", None):
        print(json.dumps(client.last_payload, indent=2, ensure_ascii=False))
    print(f"mode={'LIVE' if a.live else 'dry-run'} request_id={res.request_id} usage={res.usage}")
    for r in res.records:
        print(json.dumps(r.__dict__, ensure_ascii=False))
