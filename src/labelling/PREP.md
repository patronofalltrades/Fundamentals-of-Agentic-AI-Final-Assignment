# OpenCode Labelling — Model Client Prep (spec review)

This file is the labelling agent's (OpenCode's) prep notes for the model client and the enrichment
runs. It records the exact contracts that bind `src/labelling/model_client.py`, the `records.jsonl`
and `calls.jsonl` data, and the interface the labelling side needs from the infrastructure agent.
It is derived from the authoritative specs in `docs/specs/` and from `check_submission.py`
(vendored at repo root). It is not itself a spec.

## 1. What the infra handoff must provide (needed by OpenCode)

Per the AGENTS.md handoff #1 and the infra brief, Claude Opus must deliver, into `src/labelling/`:

- `model_client.py` — the typed interface below PLUS a mock/dry-run client (no keys) so offline
  tests run.
- `run_labelling.py <csv> --config <json> --out <dir>` — CLI entrypoint that drives the batching
  harness, exact-text cache, checkpointing, and call logging.
- `docs/INTERFACES.md` — the shared interface contract (kept by Claude Opus), including this file.

OpenCode implements the real provider client against that interface. Until it lands, OpenCode's
prep is captured here: the exact validations the checker enforces, the prompt/rubric design, the
`label_config` convention, and the exact interface signature OpenCode will implement.

### 1.1 Exact interface OpenCode expects (draft for INTERFACES.md)

`src/labelling/model_client.py` — standard library + provider SDK only for the real client. The
mock and all harness code must run with zero credentials.

```python
# --- Types ---
from dataclasses import dataclass, field
from typing import Literal, Protocol, Sequence, Mapping

Topic = Literal["access", "usability", "playback", "downloads", "catalog", "billing", "support", "other"]
Intent = Literal["complaint", "request", "praise", "cancellation", "unclear"]

@dataclass(frozen=True)
class ReviewInput:
    review_id: str
    review_text: str

@dataclass(frozen=True)
class Record:
    """One classified review. Label fields are validated by the harness after each batch."""
    review_id: str
    topic: Topic
    intent: Intent
    sentiment: float                       # finite, in [-1, 1]
    severity: int                          # exact int, 1..5
    entities: list[str] = field(default_factory=list)  # nonempty stripped strings
    evidence_quote: str = ""               # MUST be an exact substring of review_text
    needs_review: bool = False
    label_config: str = ""                 # stamped by the client = the classify_batch arg

@dataclass(frozen=True)
class CallUsage:
    model: str                             # EXACT model id, written verbatim to calls.jsonl
    input_tokens: int                      # nonneg int
    output_tokens: int                     # nonneg int

@dataclass(frozen=True)
class BatchResult:
    request_id: str                        # unique; written to calls.jsonl
    records: Sequence[Record]              # one per input review, in input order
    usage: CallUsage

class ModelClient(Protocol):
    def classify_batch(self, reviews: Sequence[ReviewInput], label_config: str) -> BatchResult:
        """Classify <=50 reviews in ONE model request. Raises on failure; returns every input ID."""
        ...

def create_client(config: Mapping) -> ModelClient:
    """Factory. `config` carries provider/model/label_config/batch/effort settings.
    Returns the real client when credentials are configured, else the mock. Never makes
    paid calls at import time."""

# --- Errors ---
class ModelClientError(Exception): ...
class TransientModelError(ModelClientError):
    """Retryable: rate limit, timeout, 5xx, network. Harness applies bounded retries w/ backoff+jitter."""
class InvalidModelOutput(ModelClientError):
    """Non-retryable structural failure: malformed JSON, missing/duplicate/mismatched IDs,
    schema-violating values. Harness does ONE invalid-output retry, then quarantine the batch."""

# --- Mock client (offline, deterministic) ---
class MockClient(ModelClient): ...   # returns canned labels, zero usage; used for dry-run + tests
```

Contract notes (OpenCode holds the labelling side; infra holds the harness):

- `classify_batch` gets the raw `review_text` (classification_input_fields == ["review_text"]) and
  returns **one Record per input review, in the same order**. Missing/extra/duplicate IDs are the
  client's bug and count as `InvalidModelOutput`.
- The client stamps `Record.label_config` = the `label_config` argument; the harness verifies it
  equals the value in the corresponding `calls.jsonl` enrich event and the completed record.
- The client returns `CallUsage` from the real provider response (or zero/None in mock); the
  harness writes `input_tokens`/`output_tokens` into `calls.jsonl`.
- Provider/effort/`label_config` come from the run `config` JSON, not hardcoded. Prompt text lives
  in `src/labelling/prompts.py` (OpenCode) versioned by the `prompt` component of `label_config`.
- The harness (infra) owns batching ≤50, exact-text cache, checkpointing, and spend limits. The
  client owns only single-request call/parse/usage.

## 2. Bounded task and enrichment prompt (role: `enrich`)

The enrichment role is a **bounded, cheap-model task**: for a batch of reviews, map each review
text into the common schema. At most **50 reviews per request**; batches must fit token/output
limits; every returned ID must be validated; results saved after each batch.

Design constraints for the prompt:

- `classification_input_fields` is `["review_text"]`. The model must classify the review text
  itself; stars (`review_rating`) and other metadata must NOT substitute for text-based intent or
  severity (stars are metadata).
- The shared rubric is injected as the system prompt:
  - `topic` ∈ `access|usability|playback|downloads|catalog|billing|support|other` with the exact
    definitions from GRADING_CONTRACT.md (highest supported severity first; on a tie, first
    specific problem; general praise is `other`; a paid-plan mention alone is not `billing`).
  - `intent` precedence: `cancellation` → `complaint` → `request` → `praise` → `unclear`.
    Bare boycott slogans / unrelated text are `unclear` unless there is a product complaint or
    explicit personal departure. General "bad app" is a complaint; do not infer a specific defect.
  - `severity` 1–5 per the shared scale. Cancellation intent or angry language alone does NOT raise
    severity. Missing context should trigger `needs_review`; never invent impact.
  - `sentiment` ∈ [-1, 1] (float), reflecting overall valence of the text.
  - `entities`: explicit feature terms supported by the text (e.g. `["ads"]`, `["shuffle"]`,
    `["lyrics"]`, `["premium"]`, `["login"]`). Nonempty strings, deduplicated.
  - `evidence_quote`: an **exact substring of the source review text** that supports the label.
    Short reviews may quote the whole text.
  - `needs_review`: boolean; true for ambiguous/unsupported-language/missing-context cases where a
    human should check the label.
- Output: one JSON object per review, keyed/labelled by `review_id`. The prompt must request
  concise structured output (cheap-model settings, no/minimal thinking where supported, capped
  output length).
- Golden labels must never enter prompts, examples, caches, or routing thresholds. Development
  records may be used for tuning; golden-informed revisions require disclosure and fresh held-out
  cases.

## 3. `label_config` convention

`label_config` is a single string that must be identical across a completed `records.jsonl` row,
its `calls.jsonl` enrich event, and any exact-text cache reuse. It must capture model + prompt +
schema version. Convention used here:

```
label_config = f"{provider}/{model}:prompt{PROMPT_VERSION}:schema{SCHEMA_VERSION}"
# example: typesafe/jev-latest:prompt-v1:schema-a5-v1
```

Provider/model decision (enrichment): **Jev direct from TypeSafe** — `jev-latest` (pins to the
exact served version once the first live call reports it; official docs price $42/Btok input,
output free). Hanif holds the TypeSafe API key (`TYPESAFE_API_KEY`). OpenRouter
(`typesafe/jev-1.13`) and BeatAPI are supported alternatives; `inception/mercury-decide:free` is a
$0 fallback if evaluated quality holds. See the Jev section below. `prompt{PROMPT_VERSION}` names
the rubric version in `src/labelling/prompts.py` (`RUBRIC_VERSION`); `schema{SCHEMA_VERSION}` is
`a5-v1` for the grading-contract schema.

Any change to model, effort, prompt, or schema bumps the string; a changed string disables cache
reuse (cache requires identical label_config). Exact model ID (`calls.jsonl` `model`) must match
what was actually called.

## 4. `records.jsonl` completed-record contract (checker-enforced)

One final record per source ID. Completed row fields and the exact checker validations:

| Field | Required type/value | Checker rule (check_submission.py audit) |
| --- | --- | --- |
| `review_id` | str, in full corpus | unknown → flagged |
| `source_sha256` | str | must equal `row_sha` of the source row (SHA-256 of canonical UTF-8 JSON of the six source fields in order; `ensure_ascii=False, separators=(",",":"), sort_keys=True`) |
| `status` | `"completed"` | `"quarantined"` also allowed with nonempty `reason` |
| `topic` | in `access,usability,playback,downloads,catalog,billing,support,other` | `invalid_schema` if not |
| `intent` | in `complaint,request,praise,cancellation,unclear` | `invalid_schema` if not |
| `sentiment` | int or float, finite, ∈ [-1,1] | `invalid_schema` if not |
| `severity` | int (exact type), 1..5 | `invalid_schema` if not |
| `entities` | list of nonempty stripped str | `invalid_schema` if not |
| `evidence_quote` | nonempty str | must be a substring of the source `review_text` (`unsupported_quote`) |
| `needs_review` | bool (exact type) | `invalid_schema` if not |
| `label_config` | nonempty str | must match the enrich call for the record (`call_config_mismatch`) |
| `cache_source_id` | optional str | must point to a direct completed original, same text, same label fields, no chain (`invalid_cache_reuse`) |

Quarantined rows: `review_id`, `source_sha256`, `status:"quarantined"`, nonempty `reason`. The 13
empty-text rows must use reason `empty_review_text`.

Every non-cached completed record must appear as a `succeeded` enrich call with the same
`label_config`; cached records need `cache_source_id`. Every completed and quarantined record needs
`source_sha256`; a mismatch is `source_mismatch`.

## 5. `calls.jsonl` contract (checker-enforced)

| Field | Rule |
| --- | --- |
| `request_id` | nonempty str, unique across file |
| `role` | one of `enrich|verify|group|memo` |
| `review_ids` | list of unique strs, all present in the full corpus; enrich: 1..50 per request |
| `model` | nonempty str (exact model ID) |
| `phase` | `initial` or `resume` (enrich) |
| `outcome` | `succeeded` or `failed` |
| `label_config` | must equal the completed records' label_config for succeeded enrich |
| `input_tokens`/`output_tokens` | nonneg ints |

Checker also requires: at least one `succeeded` call per role (enrich, verify, group, memo); no
`resume` call touching an ID already in `checkpoint_before`; `checkpoint_before` ⊆ initial-logged
(non-cached) and `checkpoint_after` strictly larger, with at least one new completed ID from a
`resume` call. Cached reuse is NOT a new API call and must not be logged as one.

## 6. Jev (System One / Decisions API) enrichment — design and constraints

**Provider decision (enrichment):** Jev is TypeSafe's System One decision model. Hanif holds a
**TypeSafe API key**, so the primary route is TypeSafe direct (its own maker). Alternatives remain
available behind the same client if needed.

| Route | Endpoint | Model id | Access |
| --- | --- | --- | --- |
| **TypeSafe (primary)** | `https://api.typesafe.ai/v1/systemone` | `jev-latest` / `jev-1.13.0` | TypeSafe API key (`TYPESAFE_API_KEY`) |
| OpenRouter | `https://openrouter.ai/api/alpha/decisions` | `typesafe/jev-1.13` / `~typesafe/jev-latest` | OpenRouter key only; per-input-token billing |
| BeatAPI (legacy) | `https://api.beatapi.io/v1/systemone` | `jev-1.13` | paid base subscription required |

OpenRouter also hosts other **decisions models with the same `state`+`questions` schema**, which
qualify as "comparably inexpensive classifiers" under COST_CALCULATOR.md if evaluated and
justified: `inception/mercury-decide:free` (free), `perplexity/pplx-decider-v1-27b`
($0.04/1M input, 262k context), `liquid/d1` ($0.04/1M). `create_client({"provider":
"openrouter", "model_alias": "mercury-decide-free"})` selects one; the same rubric/questions are
used for every model, and the chosen model is recorded in `calls.jsonl`.

**Why Jev fits the enrich role:** the Decisions API returns *typed* answers (`choice`, `score`,
`noul`) with probabilities — no prose to parse, nothing to validate semantically. We map:
`topic`→`choice`, `intent`→`choice`, `severity`→`score` (5 buckets→int 1..5), `sentiment`→`score`
(5 anchors→float −1..1), `needs_review`→`noul` (likelihood ≥ threshold). Entities and
`evidence_quote` are **code-side deterministic** (`src/labelling/extract.py`) because Jev emits no
free text; short reviews quote the whole text, longer ones quote the sentence containing a matched
feature term. This is the spec's "deterministic extraction where it works" path.

**Batching under one state (≤50 reviews/request):** one request carries a shared `state`
(`{rubric, reviews:{id:text}}`) plus five named questions per review
(`topic_<id>`, `intent_<id>`, `severity_<id>`, `sentiment_<id>`, `needs_review_<id>`). Answers come
back keyed per review, so every returned ID is validated and results are saved after each request.
`MAX_BATCH=50` is the contract ceiling; the 32k context limit binds earlier. Measured on the pilot
texts: ~830 tokens/review ⇒ **~40 reviews fit per request** (`max_batch_by_tokens` in
`model_client.py`). Full corpus (484,189 distinct nonempty texts) ⇒ ~12,105 requests at 40/req.

**CRITICAL (found and fixed in the live smoke test):** TypeSafe **does not send the question key to
the model** — the key only routes the answer. With generic instructions, every packed review gets
the *same* label (the model can't tell `topic_<id1>` from `topic_<id2>`). Each question's
`instructions` MUST name its review, e.g. *"choose the single best topic for the review stored
under the key `<id>` in state.reviews."* `prompts.build_questions` now embeds that reference; the
smoke test confirmed distinct labels before/after the fix. This also raises the per-question token
cost slightly.

**Live smoke result (TypeSafe direct, 2026-10-05):** 2 demo reviews in one request → HTTP 200,
served `jev-1.13.0`, `usage` 2143–2275 input / ~380 output tokens. Post-fix labels were distinct and
sensible (`access/complaint/sev4` vs `usability/praise/sev1`). TypeSafe does not return a request
`id`; the client generates one. `calls.jsonl` records the **served version** (`jev-1.13.0`) when the
response reports it, not the `jev-latest` alias.

**Cost (TypeSafe direct):** input-only at $42/Btok = $0.042/1M tokens, output free. Packing
amortises the rubric: measured ~1100 input tokens/review at pack 2, falling toward ~500–600/review
at larger packs. At ~500 tokens/review × 484,189 distinct texts ≈ 242M input tokens ≈ **~$10**
(exact figure from the real `cost_100` pilot). `mercury-decide:free` on OpenRouter is a $0 fallback
if evaluated quality holds. Verify with the real pilot before scaling.

**Errors (TypeSafe envelope):** 401/422 → `InvalidModelOutput` (non-retryable); 429/529 (and
5xx) → `TransientModelError` (retryable, honor `Retry-After`); malformed/missing per-review answers
→ `InvalidModelOutput`. A single bad response must never silently lose a batch: the client raises,
the harness retries the whole request, then (on repeated structural failure) splits the batch
before quarantining individual reviews.

**Client status:** `src/labelling/model_client.py` implements `ModelClient` (protocol from
section 1), `JevClient` (real, urllib-only, provider-aware: **TypeSafe primary** /
OpenRouter / BeatAPI legacy), `MockClient` (offline, deterministic, zero usage — used until a key
is configured), `create_client`, and `max_batch_by_tokens`. `src/labelling/prompts.py` holds the
rubric and per-review question builder (versioned); `extract.py` holds entities/evidence
extraction. `src/labelling/smoke_typesafe.py` is a one-call live smoke test (reads `.env`,
git-ignored). No paid call happens at import or in `create_client`.

## 7. Exact-text cache mechanics (OpenCode's responsibility in runs)

Keyed by exact `review_text` + all relevant model/effort/prompt/schema settings (i.e. identical
`label_config`). On reuse:
- each original ID keeps its own output row (business counts unchanged);
- the reused row carries `cache_source_id` = the completed original's ID, and its label fields must
  be byte-identical to the original's;
- no cache chains (the `cache_source_id` target must itself have model-call evidence, not another
  cache alias);
- no new API call is made for reused rows.

## 8. Failure, retry, and quarantine policy

- One invalid-output retry per batch element; a second invalid/structural failure → retain the ID
  with a `failed`/quarantine status and reason, keep it visible, and do NOT count it as classified.
- Transient errors: bounded retries with backoff + jitter; log every attempt with `outcome:"failed"`.
- Fallback to a stronger model is capped at a declared fraction; never auto-switch every failure to
  an expensive model.
- Nonempty text that is quarantined reduces successful classification coverage (does not count in
  the 0.6 classified-nonempty term).

## 9. Run plan (stages owned by OpenCode)

1. `cost_100` cold run: `cost_100.csv` unchanged, empty result cache, one worker, all stages
   (enrich, declared verify sample, group, rank, memo). Save `pilot_records.jsonl` + `pilot_calls.jsonl`.
2. `cost_100` warm run: same config with saved cache → zero new enrichment calls; record warm
   wall-time and incremental cost.
3. `checkpoint_500`: evaluate labels and failures, demonstrate interruption + resume with
   `checkpoint_before.json`/`checkpoint_after.json` snapshots (before nonempty, after strictly
   larger, all in completed), refresh cost/runtime estimates.
4. `analysis_10000`: refresh quality/cache/retry/throughput/cost/fallback assumptions; document a
   scaling decision within the approved budget.
5. Full corpus: account for all 660,622 IDs; classify 660,609 nonempty; quarantine 13 empty texts;
   supply records/calls into `grading/` for the exporter and evals.

No paid calls until explicit budget approval. All runs must be resumable and must not re-call
completed IDs under unchanged configuration.
