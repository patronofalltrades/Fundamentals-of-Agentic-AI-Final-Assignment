"""Versioned 25-review evidence trial on untouched scale source IDs."""

from decimal import Decimal
import json

from spotify_pipeline.codex_evidence import validate_evidence
from tools import deepinfra_recheck100 as base
from tools import openrouter_extractor_benchmark as benchmark

BATCH_SIZE = 25
OUTPUT_LIMIT = 12288  # Prior 10-review maximum was 2,879 total output tokens.
VERSION = "scale100k-revised-exact-evidence-25-trial-v1"
SCHEMA = json.loads(base.canonical(base.SCHEMA))
SCHEMA["properties"]["results"]["minItems"] = BATCH_SIZE
SCHEMA["properties"]["results"]["maxItems"] = BATCH_SIZE


def schema_for_size(size):
    if not 1 <= size <= BATCH_SIZE:
        raise ValueError("evidence batch size outside 1–25")
    schema = json.loads(base.canonical(SCHEMA))
    schema["properties"]["results"]["minItems"] = size
    schema["properties"]["results"]["maxItems"] = size
    return schema


def config_for_size(size):
    return base.digest({"version": VERSION if size == BATCH_SIZE else VERSION + "-tail-v1", "model": base.MODEL,
        "provider": base.PROVIDER, "prompt": base.INSTRUCTION,
        "schema": schema_for_size(size), "batch_size": size,
        "max_tokens": OUTPUT_LIMIT, "reasoning": "low",
        "privacy": {"only": [base.PROVIDER], "allow_fallbacks": False,
            "require_parameters": True, "data_collection": "deny", "zdr": True}})


def config_sha():
    return config_for_size(BATCH_SIZE)


def reservation_nusd():
    context = benchmark.ENDPOINT_BOUNDS["deepinfra"][0]
    return benchmark.money_nusd(Decimal(context) * base.INPUT_RATE +
        Decimal(OUTPUT_LIMIT) * base.OUTPUT_RATE)


def payload(rows):
    size = len(rows)
    schema = schema_for_size(size)
    if len({r["review_id"] for r in rows}) != size or \
            len({r["review_text"] for r in rows}) != size:
        raise ValueError("batch requires distinct IDs and exact texts")
    items = [{"review_id": r["review_id"], "source_sha": r["source_sha256"],
        "labels": {key: r["labels"][key] for key in
            ("topic", "intent", "severity", "sentiment")},
        "review_text": r["review_text"]} for r in rows]
    body = {"model": base.MODEL, "messages": [{"role": "user", "content":
        base.INSTRUCTION + json.dumps(items, ensure_ascii=False, separators=(",", ":"))}],
        "provider": {"only": [base.PROVIDER], "allow_fallbacks": False,
            "require_parameters": True, "data_collection": "deny", "zdr": True},
        "reasoning": {"effort": "low"}, "max_tokens": OUTPUT_LIMIT,
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "spotify_exact_evidence_25_trial" if size == BATCH_SIZE else
                "spotify_exact_evidence_25_tail", "strict": True,
            "schema": schema}}}
    if len(base.canonical(body).encode("utf-8")) + OUTPUT_LIMIT > \
            benchmark.ENDPOINT_BOUNDS["deepinfra"][0]:
        raise ValueError("trial request exceeds conservative context bound")
    return body


def measured_usage(response):
    if not isinstance(response, dict) or response.get("provider") != "DeepInfra" or \
            response.get("model") != base.MODEL or \
            not isinstance(response.get("id"), str) or not response["id"]:
        raise ValueError("trial response route or generation ID missing")
    usage = response.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("trial response usage missing")
    inp, out = usage.get("prompt_tokens"), usage.get("completion_tokens")
    reasoning = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
    if any(type(value) is not int or value < 0 for value in (inp, out)) or \
            inp > benchmark.ENDPOINT_BOUNDS["deepinfra"][0] or out > OUTPUT_LIMIT or \
            reasoning is not None and (type(reasoning) is not int or not 0 <= reasoning <= out):
        raise ValueError("trial usage outside full reservation")
    charge = benchmark.money_nusd(Decimal(inp) * base.INPUT_RATE +
        Decimal(out) * base.OUTPUT_RATE)
    if charge > reservation_nusd():
        raise ValueError("trial charge exceeds full reservation")
    return inp, out, reasoning, charge


def inspect(response, rows):
    size = len(rows)
    schema_for_size(size)
    if response["choices"][0].get("finish_reason") != "stop":
        raise ValueError("trial result count or finish reason differs")
    body = json.loads(response["choices"][0]["message"]["content"])
    if not isinstance(body, dict) or set(body) != {"results"} or \
            not isinstance(body["results"], list) or len(body["results"]) != size:
        raise ValueError("trial result count or shape differs")
    expected = {r["review_id"]: r for r in rows}
    accepted, invalid, seen = {}, {}, set()
    for item in body["results"]:
        if not isinstance(item, dict) or set(item) != {"review_id", "entities", "evidence_quote"}:
            raise ValueError("trial result fields differ")
        rid = item["review_id"]
        if not isinstance(rid, str) or rid not in expected or rid in seen:
            raise ValueError("unknown or repeated trial source ID")
        seen.add(rid)
        try:
            accepted[rid] = validate_evidence(expected[rid]["review_text"],
                {"entities": item["entities"], "evidence_quote": item["evidence_quote"]})
        except Exception as exc:
            invalid[rid] = type(exc).__name__ + ": " + str(exc)
    if seen != set(expected):
        raise ValueError("missing trial source ID")
    return accepted, invalid
