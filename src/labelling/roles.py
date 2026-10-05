"""Model-call wrappers for the text-generating roles: verify, group, memo.

OpenCode-owned plumbing over ``chat_client.py``. Every wrapper returns both the parsed result and
a **calls.jsonl-ready event dict** (role / review_ids / model / outcome / usage) so the harness can
log directly.

Ownership note (AGENTS.md): this file provides call plumbing and DRAFT prompts only.
- verify prompt semantics + thresholds are owned by ChatGPT (evals); the verifier must re-label
  from the original text BEFORE seeing the enrichment prediction, and must never see golden labels.
- group/memo orchestration is owned by Claude Opus (infra); these prompts consume only saved
  aggregates/bounded evidence packs.
"""

from __future__ import annotations

import json

from .chat_client import ChatClient, ChatMessage, ChatResult
from .model_client import InvalidModelOutput
from .prompts import RUBRIC

ROLE_PROMPT_VERSION = "v1"


def call_event(role, review_ids, result, outcome="succeeded", phase=None, label_config=None):
    """Build one calls.jsonl-compatible dict from a ChatResult."""
    event = {
        "request_id": result.request_id,
        "role": role,
        "review_ids": list(review_ids),
        "model": result.model,
        "outcome": outcome,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
    }
    if phase is not None:
        event["phase"] = phase
    if label_config is not None:
        event["label_config"] = label_config
    return event


# ---------------------------------------------------------------- verify ----

VERIFY_SYSTEM = (
    "You are an independent verifier for a review-labelling pipeline. Re-label the review text "
    "yourself using ONLY the rubric below and the review text. You are not shown any prior label; "
    "do not assume one exists.\n\n"
    + RUBRIC
    + "\nRespond with a single JSON object with keys: "
      "topic, intent, sentiment (float -1..1), severity (int 1-5), needs_review (bool), "
      "reason (short). No prose outside the JSON."
)

VERIFY_USER = "Review text:\n```\n{text}\n```"


def verify_review(client: ChatClient, review_id: str, review_text: str):
    """Re-label ONE review independently. Returns (labels dict, calls.jsonl event)."""
    result = client.chat(
        [ChatMessage("system", VERIFY_SYSTEM),
         ChatMessage("user", VERIFY_USER.format(text=review_text))],
        max_tokens=512,
        json_mode=True,
    )
    labels = _parse_json(result.content, f"verify:{review_id}")
    _validate_verify_labels(labels, review_id)
    return labels, call_event("verify", [review_id], result)


def verify_batch(client: ChatClient, reviews):
    """Verify a declared sample, one chat call. reviews = [(review_id, review_text), ...].

    Batched into one request for cost; each review is re-labelled independently in the prompt.
    Returns (list of (review_id, labels), calls.jsonl event).
    """
    if not reviews:
        raise InvalidModelOutput("verify_batch: empty sample")
    body = "\n".join(f"[{rid}]\n{text}\n" for rid, text in reviews)
    user = (
        "Re-label EACH review below independently per the rubric. Respond with one JSON object: "
        "a map from review_id to an object with keys topic, intent, sentiment, severity, "
        "needs_review, reason.\n\n" + body
    )
    result = client.chat(
        [ChatMessage("system", VERIFY_SYSTEM), ChatMessage("user", user)],
        max_tokens=4096,
        json_mode=True,
    )
    parsed = _parse_json(result.content, "verify:batch")
    if not isinstance(parsed, dict):
        raise InvalidModelOutput("verify:batch: expected a JSON object keyed by review_id")
    out = []
    for rid, _text in reviews:
        labels = parsed.get(rid)
        if not isinstance(labels, dict):
            raise InvalidModelOutput(f"verify:batch: missing labels for {rid}")
        _validate_verify_labels(labels, rid)
        out.append((rid, labels))
    return out, call_event("verify", [rid for rid, _ in reviews], result)


# ----------------------------------------------------------------- group ----

GROUP_SYSTEM = (
    "You name recurring complaint issues for a product analytics pipeline. Given a bounded set of "
    "example complaints (each with its review_id and quoted evidence), propose stable issue "
    "names. Rules: an issue = one recurring problem a product team could act on; merge true "
    "duplicates; never invent problems not evidenced; keep names short and specific. Respond with "
    "a single JSON object: {\"issues\": [{\"issue_id\": \"slug\", \"name\": str, "
    "\"definition\": str, \"member_review_ids\": [str, ...]}]}. member_review_ids may only contain "
    "ids from the input; every complaint id must appear exactly once."
)


def name_issues(client: ChatClient, complaint_examples):
    """Name issues from bounded complaint evidence. complaint_examples = list of
    {"review_id": rid, "topic": t, "severity": s, "evidence_quote": q}. Returns
    (issues list, calls.jsonl event)."""
    if not complaint_examples:
        raise InvalidModelOutput("name_issues: empty evidence pack")
    user = "Complaint examples (JSON):\n" + json.dumps(complaint_examples, ensure_ascii=False)
    result = client.chat(
        [ChatMessage("system", GROUP_SYSTEM), ChatMessage("user", user)],
        max_tokens=4096,
        json_mode=True,
    )
    parsed = _parse_json(result.content, "group")
    issues = parsed.get("issues") if isinstance(parsed, dict) else None
    if not isinstance(issues, list) or not issues:
        raise InvalidModelOutput("group: response missing 'issues' list")
    allowed = {ex["review_id"] for ex in complaint_examples}
    for issue in issues:
        for key in ("issue_id", "name", "definition", "member_review_ids"):
            if key not in issue:
                raise InvalidModelOutput(f"group: issue missing '{key}'")
        foreign = set(issue["member_review_ids"]) - allowed
        if foreign:
            raise InvalidModelOutput(f"group: foreign review ids {sorted(foreign)[:3]}")
    return issues, call_event("group", [], result)


# ------------------------------------------------------------------ memo ----

MEMO_SYSTEM = (
    "You write the final decision memo for a product analytics pipeline. You receive ONLY saved "
    "aggregate artifacts: the issue ranking (rank, issue_id, complaint_count, severity_sum, "
    "mean_severity, priority_score), the claims table (claim_id, issue_id, metric, value), and a "
    "bounded evidence pack of representative review quotes. Rules: every issue-level number in the "
    "memo must cite its claim_id from the claims table; do not invent numbers; describe data "
    "limits (self-selected public reviews, no revenue/retention data); state a clear "
    "recommendation with alternatives considered. Plain, direct prose."
)


def write_memo(client: ChatClient, aggregates: dict):
    """Draft the decision memo from saved aggregates. aggregates = {"ranking": [...],
    "claims": [...], "evidence": [...], "context": str}. Returns (memo text, calls.jsonl event)."""
    if not aggregates or "ranking" not in aggregates or "claims" not in aggregates:
        raise InvalidModelOutput("write_memo: aggregates must include ranking and claims")
    user = "Saved aggregates (JSON):\n" + json.dumps(aggregates, ensure_ascii=False)
    result = client.chat(
        [ChatMessage("system", MEMO_SYSTEM), ChatMessage("user", user)],
        max_tokens=4096,
    )
    return result.content, call_event("memo", [], result)


# ---------------------------------------------------------------- helpers ----

def _parse_json(text, where):
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise InvalidModelOutput(f"{where}: response is not valid JSON ({e})")


def _validate_verify_labels(labels, rid):
    from .model_client import INTENTS, TOPICS
    if labels.get("topic") not in TOPICS:
        raise InvalidModelOutput(f"verify:{rid}: bad topic {labels.get('topic')!r}")
    if labels.get("intent") not in INTENTS:
        raise InvalidModelOutput(f"verify:{rid}: bad intent {labels.get('intent')!r}")
    sev = labels.get("severity")
    if type(sev) is not int or not 1 <= sev <= 5:
        raise InvalidModelOutput(f"verify:{rid}: bad severity {sev!r}")
    sent = labels.get("sentiment")
    if not isinstance(sent, (int, float)) or not -1 <= sent <= 1:
        raise InvalidModelOutput(f"verify:{rid}: bad sentiment {sent!r}")
    if type(labels.get("needs_review")) is not bool:
        raise InvalidModelOutput(f"verify:{rid}: bad needs_review {labels.get('needs_review')!r}")