"""Deterministic, code-side extraction of ``entities`` and ``evidence_quote``.

Jev's Decisions API returns only typed values (choice/score/noul), so free-text fields are built
in code from the source review text. This is the COST_CALCULATOR.md "deterministic extraction where
it works" path: matched feature terms form the entity list; a short review's full text or the
sentence containing a matched term becomes the evidence quote.
"""

import re

ENTITY_LEXICON = {
    "login": ("login", "log in", "sign in", "sign-in"),
    "password": ("password", "passcode"),
    "signup": ("signup", "sign up", "register", "account creation"),
    "ads": ("ad ", " ads", "advert", "commercial"),
    "premium": ("premium", "paid plan", "subscription"),
    "shuffle": ("shuffle",),
    "skip": ("skip", "skipping"),
    "repeat": ("repeat",),
    "queue": ("queue",),
    "playlist": ("playlist", "play list"),
    "lyrics": ("lyric",),
    "download": ("download", "offline"),
    "crash": ("crash", "crashes", "crashed"),
    "lag": ("lag", "stutter", "buffering"),
    "audio_quality": ("audio quality", "sound quality", "quality is", "low quality"),
    "connection": ("connection", "internet", "wifi", "wi-fi", "data"),
    "update": ("update",),
    "price": ("price", "costs", "expensive", "too expensive"),
    "charge": ("charge", "charged", "charges"),
    "refund": ("refund",),
    "support": ("support", "customer service", "help center"),
    "recommendation": ("recommendation", "suggest", "suggested"),
    "search": ("search",),
}

# Feature terms to look for when we need a quote anchor, in priority order.
_ANCHOR_ORDER = (
    "lyrics",
    "download",
    "crash",
    "connection",
    "password",
    "login",
    "ads",
    "premium",
    "shuffle",
    "skip",
    "repeat",
    "queue",
    "playlist",
    "lag",
    "audio_quality",
    "price",
    "charge",
    "refund",
    "support",
    "recommendation",
    "search",
    "update",
    "signup",
)

MAX_WHOLE_TEXT_CHARS = 300


def extract_entities(review_text):
    """Return matched feature terms (stable order, deduped, nonempty)."""
    lowered = review_text.lower()
    found = []
    for term, needles in ENTITY_LEXICON.items():
        for needle in needles:
            if needle in lowered:
                found.append(term)
                break
    return found


def _split_sentences(review_text):
    parts = re.split(r"(?<=[.!?])\s+|\n", review_text)
    return [p.strip() for p in parts if p.strip()]


def extract_evidence_quote(review_text, entities):
    """Exact-source substring supporting the label.

    Short reviews: the whole original text. Longer reviews: the first sentence containing a
    matched feature term (falling back to the first sentence).
    """
    text = review_text.strip()
    if not text:
        return ""
    if len(text) <= MAX_WHOLE_TEXT_CHARS:
        return text
    sentences = _split_sentences(text)
    anchor = next((e for e in _ANCHOR_ORDER if e in entities), None)
    for sentence in sentences:
        if anchor and anchor in sentence.lower():
            return sentence
    return sentences[0] if sentences else text