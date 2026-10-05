"""Deterministic, code-side extraction of ``entities`` and ``evidence_quote``.

Jev's Decisions API returns only typed values (choice/score/noul), so free-text fields are built
in code from the source review text. This is the COST_CALCULATOR.md "deterministic extraction where
it works" path: matched feature terms form the entity list; a short review's full text or the
sentence containing a matched term becomes the evidence quote.
"""

import re

# Bump when extraction output can change; it is part of label_config (see pilot_config.json).
EXTRACT_VERSION = "extract-v2"

# Needles match whole words only (v1 matched raw substrings, so "ad " fired inside "bad ",
# "lag" inside "flag", "support" inside "unsupported"). Each needle also matches its common
# inflections (-s, -es, -ed, -ing, final-e forms); a needle ending in "*" matches any word
# that starts with it; a needle starting with "re:" is a raw regex. Multi-word needles allow
# any whitespace between words.
# "adds" is a frequent misspelling of "ads" (~8,400 full-corpus reviews), but also a verb
# ("it adds songs"). Match it unless a pronoun precedes it or a verb object follows it.
_ADDS_MISSPELLING = (
    r"(?<!\bit )(?<!\bthat )(?<!\bwhich )(?<!\bthis )(?<!\bspotify )\badds\b"
    r"(?!\s+(?:to|a|an|the|new|more|songs?|music|it|them|features?|up|that|in|on|some|your|my)\b)"
)

ENTITY_LEXICON = {
    "login": ("login", "log in", "sign in", "sign-in"),
    "password": ("password", "passcode"),
    "signup": ("signup", "sign up", "register", "account creation"),
    "ads": ("ad", "advert*", "commercial", "re:" + _ADDS_MISSPELLING),
    "premium": ("premium", "paid plan", "subscription"),
    "shuffle": ("shuffle",),
    "skip": ("skip", "skipping", "skipped"),
    "repeat": ("repeat",),
    "queue": ("queue",),
    "playlist": ("playlist", "play list"),
    "lyrics": ("lyric",),
    "download": ("download", "offline"),
    "crash": ("crash",),
    "lag": ("lag", "lagging", "laggy", "stutter", "buffering"),
    "audio_quality": ("audio quality", "sound quality", "quality is", "low quality"),
    "connection": ("connection", "internet", "wifi", "wi-fi", "data"),
    "update": ("update",),
    "price": ("price", "cost", "expensive"),
    "charge": ("charge",),
    "refund": ("refund",),
    "support": ("support", "customer service", "help center"),
    "recommendation": ("recommendation", "suggest", "suggestion"),
    "search": ("search",),
}

_SUFFIXES = r"(?:s|es|d|ed|ing|r|rs|er|ers)?"


def _needle_pattern(needle):
    if needle.startswith("re:"):
        return needle[3:]
    if needle.endswith("*"):
        return r"\b" + re.escape(needle[:-1]) + r"\w*"
    words = needle.split()
    body = r"\s+".join(re.escape(w) for w in words)
    if needle.endswith("e"):
        # Final-e verbs drop the e before -ing: update -> updating, shuffle -> shuffling.
        dropped = r"\s+".join([re.escape(w) for w in words[:-1]] + [re.escape(words[-1][:-1]) + "ing"])
        return r"\b(?:" + body + _SUFFIXES + r"|" + dropped + r")\b"
    return r"\b" + body + _SUFFIXES + r"\b"


ENTITY_PATTERNS = {
    term: re.compile("|".join(_needle_pattern(n) for n in needles), re.IGNORECASE)
    for term, needles in ENTITY_LEXICON.items()
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
    """Return matched feature terms (stable order, deduped, nonempty), whole words only."""
    return [term for term, pattern in ENTITY_PATTERNS.items() if pattern.search(review_text)]


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
        # v1 searched for the entity *name* ("ads", "audio_quality"); match its needles instead.
        if anchor and ENTITY_PATTERNS[anchor].search(sentence):
            return sentence
    return sentences[0] if sentences else text