"""Shared labelling rubric and question templates for the Jev (Decisions API) enrichment role.

The rubric text is placed once in the request ``state``; per-review questions stay terse and
reference it. Versioned by the ``prompt`` component of ``label_config``.
"""

RUBRIC_VERSION = "v2"  # v2: topic criteria and topic instruction (ported from Codex jev-rubric-v2)

RUBRIC = """SPOTIFY REVIEW LABELLING RUBRIC
Classify the review text itself. Stars/ratings and other metadata are NOT inputs to intent or
severity; they must never substitute for interpreting the text.

TOPIC (choose exactly one):
- access: Login, signup, password or account access.
- usability: Navigation, controls, layout, queue/playlist management, ad interruptions.
- playback: Playback failure, crashes, lag, connection failures, audio quality, resource use.
- downloads: Downloading, saved music, offline listening, disappearing downloads.
- catalog: Missing songs/artists, search/discovery, recommendations, lyrics availability.
- billing: Price, charges, subscriptions, paywalls, premium entitlement; explicitly premium-only controls go here.
- support: Contacting support and the support response.
- other: General praise/criticism, unrelated content, or no supported specific topic.
Rules: Choose the problem with the highest supported severity; on a tie choose the first specific
problem mentioned. For a positive review choose the first specific praised feature; general praise
is 'other' (generic "great music app" praise is 'other'). Mentioning a paid plan alone is not
'billing'; an explicitly premium-only control is 'billing'. A subscription failing to activate is
'billing'; music crashing for a paying customer is 'playback'. Ad interruptions are 'usability';
loading failures are 'playback'; missing (including offline) lyrics are 'catalog'. 'support' means
contact with customer service, not support for a cause.

INTENT (choose the highest-precedence one that applies): cancellation > complaint > request > praise > unclear
- cancellation: Explicitly leaving, uninstalling, cancelling, or threatening to do so.
- complaint: Negative experience, including mixed praise/criticism.
- request: Desired change without a reported failure.
- praise: Positive statement.
- unclear: Bare boycott slogans, unrelated/meaningless text, or no product complaint / explicit personal departure.
Rules: General 'bad app' is a complaint; do not infer a specific defect. A boycott slogan with no
product complaint is 'unclear'.

SEVERITY (choose the highest supported severity):
1 - No reported problem: praise, neutral/unclear content, or a pure feature request.
2 - Dislike, generic criticism, minor annoyance, or a cosmetic issue; no supported functional loss.
3 - A degraded or restricted function; some use or workaround remains.
4 - A clearly blocked core task, such as inability to log in or play music.
5 - Explicit serious financial, privacy, or data harm. An expensive plan, a crash, or angry language alone is insufficient.
Rules: Cancellation intent does not automatically raise severity. Missing context should trigger
needs_review; do not invent impact.

SENTIMENT: a value from -1 (very negative) through 0 (neutral) to +1 (very positive), reflecting
the overall valence of the text.

NEEDS_REVIEW: true when the text is ambiguous, in an unsupported language, or context is too thin
to label confidently; do not invent impact.
"""

TOPIC_GLOSS = {
    "access": "Login, signup, passwords, or account access.",
    "usability": "Navigation, layout, controls, queue or playlist management, or ad interruptions.",
    "playback": "Playing, pausing, skipping, shuffling, crashes, loading failures, lag, audio or connection failures, or resource use.",
    "downloads": "Downloading music, saved downloads, offline listening, or disappearing downloads.",
    "catalog": "Missing music, artists, or podcasts; search, discovery, recommendations, or lyrics availability, including missing offline lyrics.",
    "billing": "Prices, charges, subscriptions, paywalls, premium entitlement, or explicitly premium-only controls. A paid-plan mention alone is not billing.",
    "support": "Contact with customer service or its response, not support meaning endorsement of a cause.",
    "other": "General praise or criticism, unrelated or unclear text, or no supported specific product topic. Generic 'great music app' praise is other.",
}

TOPIC_INSTRUCTIONS = (
    "Choose only a product topic supported by the review text. For multiple problems, choose the "
    "highest supported severity; on a tie, choose the first specific problem mentioned. For a positive "
    "review, choose the first specific praised feature; general praise is other. A Premium mention "
    "alone is not billing; an explicitly premium-only control is billing. Ad interruptions are "
    "usability, loading failures are playback, and missing offline lyrics are catalog."
)

INTENT_GLOSS = {
    "cancellation": "explicitly leaving, uninstalling, cancelling, or threatening to",
    "complaint": "negative experience, including mixed praise/criticism",
    "request": "desired change without a reported failure",
    "praise": "positive statement",
    "unclear": "boycott slogan, unrelated/meaningless text, no product complaint/departure",
}

SEVERITY_SCALE = [
    "1 - no reported problem (praise, neutral/unclear, or pure feature request)",
    "2 - dislike, generic criticism, minor annoyance, cosmetic; no functional loss",
    "3 - degraded or restricted function; some use or workaround remains",
    "4 - a clearly blocked core task, e.g. cannot log in or play music",
    "5 - explicit serious financial, privacy, or data harm",
]

SENTIMENT_SCALE = [
    "-1 very negative",
    "-0.5 negative",
    "0 neutral",
    "0.5 positive",
    "+1 very positive",
]

NEEDS_REVIEW_CRITERIA = {
    "true": "Ambiguous, unsupported language, or too little context to label confidently.",
    "false": "The text clearly supports confident labels.",
}


def build_questions(review_id):
    """Terse per-review questions. Full definitions live in state.rubric.

    The question *key* is not sent to the model, so each instruction must name the review it is
    about using the path into ``state.reviews``; otherwise a packed batch applies the same answer
    to every review.
    """
    target = f"the review stored under the key `{review_id}` in state.reviews"
    q = {
        "topic": {
            "type": "choice",
            "instructions": f"Using state.rubric, for {target}: {TOPIC_INSTRUCTIONS}",
            "criteria": TOPIC_GLOSS,
        },
        "intent": {
            "type": "choice",
            "instructions": f"Using state.rubric, choose the highest-precedence intent for {target}.",
            "criteria": INTENT_GLOSS,
        },
        "severity": {
            "type": "score",
            "instructions": f"Using state.rubric, choose the highest supported severity for {target}.",
            "criteria": SEVERITY_SCALE,
        },
        "sentiment": {
            "type": "score",
            "instructions": f"Using state.rubric, score the overall sentiment of {target}.",
            "criteria": SENTIMENT_SCALE,
        },
        "needs_review": {
            "type": "noul",
            "instructions": f"Using state.rubric, should a human review the labels of {target}?",
            "criteria": NEEDS_REVIEW_CRITERIA,
        },
    }
    return {f"{name}_{review_id}": spec for name, spec in q.items()}