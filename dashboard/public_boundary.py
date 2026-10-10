"""The approved public presentation boundary for the accepted-evidence import.

Contract: "Approved public presentation boundary" in ``docs/accepted-evidence-dashboard-import.md`` of the
pipeline worktree. Code here decides, at import time, what a public API response may carry:

1. An excerpt has at most 30 words. A longer quote is cut and marked shortened. The exact quote stays private.
2. An excerpt that the screen below finds personal information in is never public.
3. Each public record has an opaque random reference. Its mapping to the row stays in the private database.
4. Nonaccepted rows appear only as counts of sanitized reason categories.

The personal-information screen is automatic and conservative. It is not a human review. Besides emails,
links, handles and long numbers, it treats a capitalized word as a possible name when its lowercase form is rare
in the accepted quotes (``vocabulary``). It cannot catch a name that is also a common word, or a name in
another script.
"""

import re
import secrets
from collections import Counter

MAX_EXCERPT_WORDS = 30
SHORTENED_MARK = "…"

_PERSONAL = (
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),                    # email address
    re.compile(r"(?i)\b(?:https?://|www\.)\S+"),                # link
    re.compile(r"(?<![\w@])@\w{2,}"),                           # social handle
    re.compile(r"(?i)\b(?:my name is|i am called|call me at|text me at)\b"),
    re.compile(r"\b[A-Z][a-z]+[._][A-Z][a-z]+\b"),             # First.Last or First_Last
)
_DIGITS = re.compile(r"\+?\d[\d\s().-]{5,}\d")  # phone, card or account numbers: checked by digit count
MIN_PERSONAL_DIGITS = 7
_CAPITALIZED = re.compile(r"\b[A-Z][a-z']+\b")
_LOWER = re.compile(r"\b[a-z][a-z']+\b")
MIN_COMMON_LOWERCASE = 3  # a capitalized word seen in lowercase fewer times than this may be a name
SCREEN_VERSION = "personal-info-screen-v2: email, link, handle, 7+ digit number, name phrase, First.Last, " \
                 "capitalized word seen in lowercase fewer than 3 times in the accepted quotes"


def vocabulary(texts):
    """Lowercase word counts, used to tell common capitalized words from possible names."""
    counts = Counter()
    for text in texts:
        counts.update(_LOWER.findall(text))
    return counts


def excerpt(quote):
    """``(text, shortened)``: the quote when it has at most 30 words, else its first 30 words and a mark."""
    words = quote.split()
    if len(words) <= MAX_EXCERPT_WORDS:
        return quote, False
    return " ".join(words[:MAX_EXCERPT_WORDS]) + " " + SHORTENED_MARK, True


def has_personal_info(text, common=None):
    """True when the text may hold personal information. ``common`` is a ``vocabulary()`` of the corpus."""
    if any(p.search(text) for p in _PERSONAL):
        return True
    if common is not None and any(common.get(w.lower(), 0) < MIN_COMMON_LOWERCASE for w in _CAPITALIZED.findall(text)):
        return True
    return any(sum(ch.isdigit() for ch in m.group(0)) >= MIN_PERSONAL_DIGITS for m in _DIGITS.finditer(text))


def new_ref():
    """An opaque public reference: random, so it reveals nothing about the ID, position or hash."""
    return "r" + secrets.token_hex(8)


REF_RE = re.compile(r"^r[0-9a-f]{16}$")

# Sanitized reason categories. Free-form reasons, exceptions and provider messages stay private.
REASON_CATEGORIES = {
    "awaiting_label": "Awaiting a label",
    "empty_text": "No review text",
    "evidence_quote_check_failed": "Evidence quote failed the source check",
    "entity_check_failed": "Entities failed the source check",
    "batch_id_check_failed": "Batch source IDs failed the check",
    "other_output_check_failed": "Other output check failed",
    "repeat_of_quarantined_text": "Repeats a quarantined text",
    "delivery_unconfirmed": "Request delivery not confirmed",
    "repeat_of_unresolved_text": "Repeats an unresolved text",
}


def reason_category(source_state, reason):
    """One sanitized category for a nonaccepted row, from its saved state and reason."""
    if source_state == "eligible_or_awaiting_label":
        return "awaiting_label"
    if source_state == "empty_text":
        return "empty_text"
    r = (reason or "").lower()
    if source_state == "quarantined":
        if "alias" in r or "exact text" in r or "exact_text" in r:
            return "repeat_of_quarantined_text"
        if "source id" in r or "source_i" in r:
            return "batch_id_check_failed"
        if "evidence quote" in r:
            return "evidence_quote_check_failed"
        if "entit" in r:
            return "entity_check_failed"
        return "other_output_check_failed"
    if source_state == "uncertain_direct" or (source_state == "uncertain" and "delivery" in r):
        return "delivery_unconfirmed"
    return "repeat_of_unresolved_text"
