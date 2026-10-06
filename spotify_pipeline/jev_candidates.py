"""Offline source-span candidates for a possible Jev evidence selector.

No model or provider call occurs here. Candidate text always comes from the
original review. This prototype is intentionally separate from saved evidence.
"""

import re
import math
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .codex_evidence import _whole_entity_span, validate_evidence
from .errors import ValidationError

VERSION = "jev-candidates-v1"
MAX_ENTITY_CANDIDATES = 96
MAX_QUOTE_CANDIDATES = 16
_CLAUSE_END = re.compile(r"[.!?;\n。！？；]+")
_QUOTED = re.compile(r"[\"“‘'«](.{1,100}?)[\"”’'»]")
_VERSION = re.compile(r"(?<!\w)\d+(?:\.\d+){1,3}(?!\w)")
_DEVICE = re.compile(r"(?<!\w)[^\W\d_][\w-]{1,24}[- ]?\d+[\w-]{0,12}(?!\w)", re.UNICODE)
_ENGLISH_FUNCTION = frozenset(
    "a an and are as at be been but by for from had has have i in is it my of on or "
    "our the their them there these this those to was were with you your".split())


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Candidates:
    entities: Tuple[Span, ...]
    quotes: Tuple[Span, ...]
    entity_total: int
    quote_total: int
    entity_truncated: bool
    quote_truncated: bool


def _is_word(char: str) -> bool:
    return char == "_" or char.isalnum() or unicodedata.category(char).startswith("M")


def _words(text: str) -> List[Tuple[int, int]]:
    out = []
    start = None
    for index, char in enumerate(text):
        if _is_word(char):
            if start is None:
                start = index
        elif start is not None:
            out.append((start, index))
            start = None
    if start is not None:
        out.append((start, len(text)))
    return out


def _span(text: str, start: int, end: int) -> Span:
    return Span(start, end, text[start:end])


def _trimmed(text: str, start: int, end: int) -> Span:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return _span(text, start, end)


def _rank_entity(span: Span, word_count: int, special: int) -> Tuple[int, int, int, int]:
    parts = span.text.split()
    edge_penalty = sum(p.lower() in _ENGLISH_FUNCTION for p in (parts[0], parts[-1])) if parts else 0
    case_or_digit = any(c.isupper() or c.isdigit() for c in span.text)
    # Generic linguistic clues only. Do not add Spotify or saved-answer terms.
    score = (special * 12 + (4 if case_or_digit else 0) +
             (3 if 2 <= word_count <= 4 else 0) - 4 * edge_penalty -
             (2 if len(span.text) <= 2 else 0))
    return score, -abs(word_count - 2), -span.start, -span.end


def generate(text: str) -> Candidates:
    """Return bounded, exact spans and explicit truncation facts."""
    if not isinstance(text, str) or not text.strip():
        raise ValidationError("candidate generation needs nonempty review text")
    words = _words(text)
    entities: Dict[Tuple[int, int], Tuple[Span, int, int]] = {}

    def add_entity(start: int, end: int, count: int, special: int = 0) -> None:
        span = _trimmed(text, start, end)
        if not span.text or not _whole_entity_span(text, span.start, span.end):
            return
        key = (span.start, span.end)
        current = entities.get(key)
        if current is None or special > current[2]:
            entities[key] = (span, count, special)

    for index in range(len(words)):
        for count in range(1, 6):
            last = index + count - 1
            if last >= len(words):
                break
            start, end = words[index][0], words[last][1]
            # A candidate cannot cross a hard sentence boundary.
            if _CLAUSE_END.search(text[start:end]):
                break
            add_entity(start, end, count)
    for match in _QUOTED.finditer(text):
        add_entity(*match.span(1), len(_words(match.group(1))), special=2)
    for pattern in (_VERSION, _DEVICE):
        for match in pattern.finditer(text):
            add_entity(*match.span(), len(_words(match.group())), special=2)
    # Whitespace units preserve punctuation-bearing names such as C++ and plan+.
    for match in re.finditer(r"\S+", text):
        start, end = match.span()
        while start < end and unicodedata.category(text[start]).startswith("P"):
            start += 1
        while end > start and unicodedata.category(text[end - 1]).startswith("P"):
            end -= 1
        if start < end and any(not _is_word(ch) for ch in text[start:end]):
            add_entity(start, end, len(_words(text[start:end])), special=1)

    ranked = sorted(entities.values(), key=lambda item: _rank_entity(*item), reverse=True)
    selected = sorted((item[0] for item in ranked[:MAX_ENTITY_CANDIDATES]),
                      key=lambda span: (span.start, span.end))

    quotes: Dict[Tuple[int, int], Span] = {}

    def add_quote(start: int, end: int) -> None:
        span = _trimmed(text, start, end)
        if span.text:
            quotes[(span.start, span.end)] = span

    add_quote(0, len(text))
    start = 0
    for match in _CLAUSE_END.finditer(text):
        add_quote(start, match.start())
        start = match.end()
    add_quote(start, len(text))
    for match in _QUOTED.finditer(text):
        add_quote(*match.span(1))
    for index in range(0, len(words), 6):
        last = min(index + 12, len(words)) - 1
        if last >= index:
            add_quote(words[index][0], words[last][1])
    full = _trimmed(text, 0, len(text))
    others = [s for s in quotes.values() if s != full]
    others.sort(key=lambda s: (len(s.text), s.start, s.end))
    quote_selected = [full] + others[:MAX_QUOTE_CANDIDATES - 1]
    return Candidates(tuple(selected), tuple(quote_selected), len(entities),
                      len(quotes), len(entities) > MAX_ENTITY_CANDIDATES,
                      len(quotes) > MAX_QUOTE_CANDIDATES)


def build_request(text: str, labels: Dict[str, object], *, diagnostic: bool = False) -> Tuple[Dict[str, object], Candidates]:
    """Build an offline Jev-compatible request; refuse cap loss by default."""
    found = generate(text)
    if (found.entity_truncated or found.quote_truncated) and not diagnostic:
        raise ValidationError("candidate cap exceeded; request requires review or a new strategy")
    required = ("topic", "intent", "severity", "sentiment")
    if any(key not in labels for key in required):
        raise ValidationError("candidate request needs frozen labels")
    state = {"review_text": text, "predicted_labels": {key: labels[key] for key in required}}
    options = {"q%02d" % index: span.text for index, span in enumerate(found.quotes)}
    options["none"] = "No candidate supports the predicted labels"
    questions: Dict[str, object] = {
        "quote": {"type": "choice", "instructions": "Pick one exact quoted span that supports the predicted labels, or none.",
                  "criteria": options},
        "support_exists": {"type": "noul", "instructions": "Does any text in this review directly support the predicted labels?"},
    }
    for index, span in enumerate(found.entities):
        questions["e%02d" % index] = {
            "type": "noul",
            "instructions": {"question": "Is this exact span a relevant named product, feature, plan, or problem?",
                             "candidate": span.text, "start": span.start, "end": span.end},
        }
    return {"state": state, "model": "jev-1.13.0", "questions": questions}, found


def select_evidence(text: str, found: Candidates, response: Dict[str, object]) -> Dict[str, object]:
    """Decode typed choices without creating evidence on abstention or cap loss."""
    if not isinstance(response, dict) or response.get("model") != "jev-1.13.0":
        raise ValidationError("unexpected evidence model")
    answers = response.get("answers")
    expected = {"quote", "support_exists"} | {"e%02d" % i for i in range(len(found.entities))}
    if not isinstance(answers, dict) or set(answers) != expected:
        raise ValidationError("evidence answer set differs from request")
    quote = answers["quote"]
    if not isinstance(quote, dict) or quote.get("type") != "choice":
        raise ValidationError("invalid quote choice")

    def probability(answer: object) -> float:
        if not isinstance(answer, dict) or answer.get("type") != "noul":
            raise ValidationError("invalid Noul answer")
        value = answer.get("noul")
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValidationError("invalid Noul probability")
        return float(value)

    exists = probability(answers["support_exists"])
    scored = [(span, probability(answers["e%02d" % i]))
              for i, span in enumerate(found.entities)]
    flags = []
    if found.entity_truncated:
        flags.append("entity_candidates_truncated")
    if found.quote_truncated:
        flags.append("quote_candidates_truncated")
    if exists < 0.5:
        flags.append("support_abstain")
    selected = quote.get("choice")
    if selected == "none":
        flags.append("quote_abstain")
    elif not isinstance(selected, str) or not re.fullmatch(r"q\d{2}", selected) or int(selected[1:]) >= len(found.quotes):
        raise ValidationError("quote choice is not a supplied candidate")
    entities = []
    seen = set()
    for span, value in scored:
        if value >= 0.8 and span.text not in seen:
            seen.add(span.text)
            entities.append(span.text)
    if len(entities) > 10:
        flags.append("entity_overflow")
    if flags:
        return {"status": "abstained", "flags": flags, "evidence": None}
    chosen = found.quotes[int(selected[1:])]
    evidence = validate_evidence(text, {"entities": entities, "evidence_quote": chosen.text})
    return {"status": "selected", "flags": [], "evidence": evidence}
