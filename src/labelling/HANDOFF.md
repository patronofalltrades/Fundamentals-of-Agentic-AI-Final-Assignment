# Handoff to Claude Opus (infra): what `run_labelling.py` needs to drive

From OpenCode (labelling). This is the short version; the full contract is `src/labelling/PREP.md`
and the drafted interface in its section 1. Keep `docs/INTERFACES.md` as the source of truth.

## Call surface (already implemented in `src/labelling/model_client.py`)

```python
from labelling.model_client import create_client, max_batch_by_tokens, ReviewInput
from labelling.model_client import TransientModelError, InvalidModelOutput

client = create_client({"provider": "typesafe"})     # -> JevClient (needs TYPESAFE_API_KEY)
# or create_client({}) with no key -> MockClient (offline dry-run)

reviews = [ReviewInput(review_id=rid, review_text=text), ...]   # chunk size from max_batch_by_tokens
result = client.classify_batch(reviews, label_config)           # -> BatchResult
result.request_id, result.records, result.usage
#   result.records: list[Record] with topic,intent,sentiment,severity,entities,evidence_quote,
#                   needs_review,label_config  (exact grading-contract field set)
#   result.usage:   CallUsage(model, input_tokens, output_tokens)  # model = served version
```

- **Chunking:** `n = max_batch_by_tokens(texts)` (currently **36**; hard cap 50). Do not exceed it;
  the 32k context is the binding limit.
- **Do not re-implement prompts.** `prompts.build_questions` already embeds the per-review reference
  in each question's `instructions`; this is required because **TypeSafe does not send the question
  key to the model** (without it, packed reviews get identical labels).
- **label_config:** `"typesafe/jev-latest:prompt-v1:schema-a5-v1"`. Must be identical in the
  completed `records.jsonl` row and the enrich `calls.jsonl` event. A change invalidates the cache.

## Error handling the harness must implement

| Raised | Meaning | Harness action |
| --- | --- | --- |
| `TransientModelError` (429/5xx) | rate limit / transient | bounded retries, backoff + jitter, honor `Retry-After`; log every attempt `outcome:"failed"` |
| `InvalidModelOutput` (401/422, bad answers) | non-retryable | one retry, then split the batch; quarantine individual IDs with a reason |
| `ModelClientError` base (e.g. 402 credits) | stop | halt the run, surface the reason |

Single bad response must not silently lose a whole batch: retry → split → quarantine.

## Outputs the harness writes (per grading contract)

- `records.jsonl` (completed + quarantined), `calls.jsonl` (role/phase/outcome/label_config/usage),
  `checkpoint_before.json` / `checkpoint_after.json` (`{"completed_ids": [...]}`, before ⊂ after).
- Enrich `review_ids` must be 1..50 unique; `phase` = `initial` (cold) or `resume` (warm);
  no `resume` call may touch a `checkpoint_before` ID.
- Cached reuse sets `cache_source_id` to a direct completed original; it is **not** a new API call.

## Pilot

- Config: `src/labelling/pilot_config.json` (cold + warm runs, `cost_100.csv`, 1 worker).
- Money: run **cold then warm** only after Hanif approves the budget
  (`limits.spend_cap_usd` = $1.00; measured cold cost is a fraction of a cent).
- `pilot_records.jsonl` / `pilot_calls.jsonl` go in `cost/` (yours); records/calls data come from
  the labelling run.
