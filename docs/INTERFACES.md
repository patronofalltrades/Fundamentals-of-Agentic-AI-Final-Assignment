# INTERFACES — shared contract for the three agents

Owner: Claude Opus (infrastructure). Specs in `docs/specs/` and `check_submission.py` are authoritative; this file says how our code meets them. If you need a change, add a note under "Change requests" at the bottom instead of editing another agent's files.

Runtime: **Python 3.9+, standard library only** (graders run `python3` — 3.9.6 on macOS). Use `from __future__ import annotations`; no `match`, no `X | Y` at runtime. Tests use `unittest`: `python3 -m unittest discover -s tests -t .`.

## 1. Layout

```
check_submission.py        vendored grader (byte-identical, sha256 d60bd66d…)
run_pipeline.py            CLI: full pipeline (ingest → enrich → verify → group → rank → memo)
run_labelling.py           CLI: enrich only (alias of run_pipeline.py --stages enrich) — OpenCode uses this
export_grading.py          CLI: run dir → grading/ folder
src/pipeline/              infra modules (Claude Opus)
  rowhash.py               FIELDS, TOPICS, INTENTS, canonical(), row_sha(), file_sha256()  (byte-identical to the checker)
  io.py                    atomic_write_json/text, append_jsonl (flush+fsync), read_jsonl
  prepare.py               stream CSV, profile, exact-text index, pending queue
  state.py                 RecordStore, checkpoints
  spend.py                 RateLimiter, SpendLedger, retry/backoff
  enrich.py                batching harness, cache, validation, retry→split→quarantine
  clients.py               builds enrich/chat clients from config; refuses mock in non-dry-run
  verify.py group.py rank.py claims.py memo.py export.py
src/labelling/             OpenCode: model_client.py (contract below), prompts, chat_client.py, roles.py
evals/                     ChatGPT: golden labels, verifier prompt, reports
cost/                      calculator + pilot evidence
grading/                   generated export (only ingestion.json is committed until the full run)
runs/                      run directories (git-ignored, except selected evidence copied out)
tests/                     unittest suites, one file per module
```

## 2. Enrichment client contract (implemented by OpenCode in `src/labelling/model_client.py`)

```python
@dataclass(frozen=True) class ReviewInput:  review_id: str; review_text: str
@dataclass(frozen=True) class Record:       review_id, topic, intent, sentiment: float, severity: int,
                                            entities: list[str], evidence_quote: str, needs_review: bool, label_config: str
@dataclass(frozen=True) class CallUsage:    model: str; input_tokens: int; output_tokens: int
                                            # optional extra attrs read with getattr(..., None):
                                            # cached_input_tokens, reasoning_tokens, cost_usd, provider
@dataclass(frozen=True) class BatchResult:  request_id: str; records: Sequence[Record]; usage: CallUsage

class ModelClient(Protocol):
    def classify_batch(self, reviews: Sequence[ReviewInput], label_config: str) -> BatchResult: ...

class ModelClientError(Exception)          # stop the run, surface the reason (e.g. 402 credits)
class TransientModelError(ModelClientError)  # 429/5xx/timeout: bounded retries; may carry .retry_after (seconds)
class InvalidModelOutput(ModelClientError)   # 4xx/malformed: one retry, then split, then quarantine
create_client(config: dict) -> ModelClient   # returns MockClient when no key is set
```

The harness treats the client as untrusted: it re-validates every record (section 5) and never trusts the client's own checks.

**Mock guard.** `create_client` silently returns `MockClient` when no key is set. `pipeline.clients` therefore requires `--dry-run` for any mock client, and in dry-run forces `label_config = "mock:" + label_config` and `model = "mock"`. A non-dry-run run with a mock client aborts before any work.

## 3. Chat roles contract (verify / group / memo)

Infra calls a chat client through this duck-typed interface (OpenCode's `chat_client.py` provides the real one; `pipeline.clients.MockChat` is the offline one):

```python
chat.complete(messages: list[dict], *, max_tokens: int, temperature: float = 0.0, response_format: str | None = None)
    -> ChatResult(text: str, request_id: str, model: str, input_tokens: int, output_tokens: int,
                  cached_input_tokens: int | None = None, cost_usd: float | None = None)
```

If OpenCode's client differs, `pipeline.clients` adapts it; role modules depend only on the shape above. Prompts for verify belong to ChatGPT (`evals/verifier_prompt.md`, loaded at runtime if present; infra ships a draft default).

## 4. Run directory (`runs/<name>/`) — written by run_pipeline.py, read by export/cost

| File | Format |
|---|---|
| `run_config.json` | resolved config snapshot + input csv path, file sha256, label_config, dry_run flag |
| `records.jsonl` | **append-only**; one line per state change; the **last** line per `review_id` wins. Same shape as the grading record (below) |
| `calls.jsonl` | append-only, one line **per attempt** (failed attempts included) |
| `invocations.jsonl` | one line per CLI invocation: `{invocation_id, phase, started_at, ended_at, wall_seconds, stop_reason, stages, counts}` |
| `checkpoints/<invocation_id>-start.json`, `-end.json` | `{"completed_ids": [...]}` sorted; written atomically |
| `verify/sample.json`, `verify/labels.jsonl`, `verify/report.json` | verifier sample IDs, verifier labels, agreement/disagreement report |
| `group/issues.json`, `group/membership.csv` | issues `[{issue_id, name, description, topic, rule}]`; `issue_id,review_id` |
| `rank/ranking.csv`, `rank/claims.csv` | grading formats |
| `memo/inputs.json`, `memo/memo.md` | saved aggregate pack given to the memo role; the memo |
| `ledger.json` | spend ledger summary (spent, reserved, cap, by role) |

**Record line** (completed):
```json
{"review_id":"…","source_sha256":"…","status":"completed","topic":"playback","intent":"complaint","sentiment":-0.6,"severity":4,"entities":["crash"],"evidence_quote":"…exact substring…","needs_review":false,"label_config":"…"}
```
plus optional `"cache_source_id":"<direct original id>"`. Quarantined: `{"review_id","source_sha256","status":"quarantined","reason"}`; reasons: `empty_review_text`, `invalid_model_output:<detail>`, `missing_from_response`, `retries_exhausted:<detail>`. Pending IDs have no line.

**Call line** (grading fields first, extras allowed):
```json
{"request_id":"…","role":"enrich","review_ids":["…"],"model":"jev-1.13.0","phase":"initial","outcome":"succeeded","label_config":"…","input_tokens":2275,"output_tokens":382,
 "invocation_id":"…","attempt":1,"started_at":"ISO8601Z","ended_at":"…","duration_ms":812,"provider":"typesafe","error":null,
 "cached_input_tokens":null,"reasoning_tokens":null,"cost_usd":null}
```
- `request_id` must be unique across the file: use the provider id when present, else `local-<uuid4>`; on collision append `#<attempt>`.
- Failed attempts: `outcome:"failed"`, tokens `0` unless the provider reported usage, `error` set.
- `phase` is per invocation: `initial` if the store had no completed records when the invocation started, else `resume`. Verify/group/memo calls also carry the invocation phase.
- Never log a cache reuse as a call.

## 5. Harness rules (enrich)

- Pending = IDs with no completed record under the current `label_config` (and not `empty_review_text`). Empty texts are written as quarantined in the ingest step, never sent.
- **Exact-text cache:** key = (`review_text` exact string, `label_config`). The first ID in file order for a text is the original and is sent. Others get a copy of the original's label fields + `cache_source_id = original_id` once the original completes. Originals never carry `cache_source_id` (no chains). The cache index is rebuilt from `records.jsonl` on start (only non-cached completed records with the same `label_config`).
- Batches: ≤ `max_reviews_per_request` (hard max 50), optional token-budget sizing via the client's `max_batch_by_tokens` if present.
- Per-record validation: ID was in the request, no duplicates; `topic∈TOPICS`, `intent∈INTENTS`, `severity` int 1..5 (bool rejected), `sentiment` finite in [-1,1], `entities` list of non-blank str, `evidence_quote` non-blank and a substring of the exact source text, `needs_review` bool, `label_config` equals the run's.
- Failure handling: `TransientModelError` → bounded retries with exponential backoff + full jitter, honor `retry_after`; `InvalidModelOutput` → one retry, then split the batch in half recursively; a single-review batch that still fails is quarantined with a reason. IDs missing from an otherwise good response are retried in a new batch, then quarantined (`missing_from_response`). `ModelClientError` (base) → stop the invocation cleanly (`stop_reason`).
- Save after every batch: append records, then calls; flush+fsync. A crash can lose at most the in-flight batch.
- Interruption: `--max-batches N` stops after N successful batches (deterministic demo); SIGINT stops admitting work, finishes or abandons in-flight calls, writes the end checkpoint. On restart, completed IDs are never re-sent under the same `label_config`.
- Concurrency: `workers` threads share one `RateLimiter` (requests/min, tokens/min) and one `SpendLedger`. Before dispatch, reserve worst-case cost; stop admitting when `spent + reserved + next > spend_cap_usd`. Timeouts are flagged `uncertain_charge: true` in the call line.
- Golden-50 labels never enter prompts, caches or thresholds. Golden **texts** are part of the full run like any other row.

## 6. Downstream stages

- **verify:** deterministic sample = completed, non-cached records whose `sha256(review_id)` falls under `sample_fraction` (default 0.05, min 20, max `max_items`). The verifier sees only `(review_id, review_text)`, never the enrich prediction or golden labels. Report: per-field agreement (topic, intent, severity exact and ±1), confusion pairs, list of disagreements. Verify does not change records (it is evidence and feeds `needs_review` analysis only).
- **group:** code assigns every completed `complaint`/`cancellation` record to exactly one issue. `issue_id` = `<topic>.<theme>` (lowercase ASCII, stable across runs), where `theme` comes from a fixed, versioned keyword table per topic applied to `entities` + `review_text`, falling back to `<topic>.general`. The group model role only **names and describes** issues from a bounded evidence pack (≤ N quotes per issue, ≤ M issues); its output is validated (unknown/duplicate issue IDs rejected; missing names fall back to a deterministic name). It never changes membership.
- **rank:** exactly the checker's arithmetic: `complaint_count`, `severity_sum`, `mean_severity` = Decimal half-up to 6 dp, `priority_score = severity_sum`; sort by `(-priority_score, issue_id)`; rank from 1. All numbers written as strings exactly like `str()` of the checker's values.
- **claims:** `claim_id = C<rank:03d>-<metric>` for every ranked issue × the 4 metrics; values identical to ranking.csv.
- **memo:** inputs = ranking (top N), claims, issue names, ≤3 evidence quotes per issue, coverage numbers, verify agreement. The memo must cite claim IDs like `[C001-severity_sum]`. Offline/dry-run mode writes a deterministic template memo from the same inputs.

## 7. Grading export (`export_grading.py --run runs/<name> --csv <full.csv> --out grading [--gzip] --checkpoint-before P --checkpoint-after P`)

Writes `run.json` (exact contract JSON), `ingestion.json` (via `check_submission.profile`), `records.jsonl[.gz]` (one line per CSV ID in CSV order: latest completed, else latest quarantined, else `{"status":"quarantined","reason":"not_processed"}`), `membership.csv`, `ranking.csv`, `claims.csv`, `calls.jsonl[.gz]`, `checkpoint_before.json`, `checkpoint_after.json`. Then optionally runs the checker (`--self-check`) and writes `self-check.json` **outside** `grading/`.

## 8. Cost calculator (`cost/`)

`python3 cost/cost_calc.py` (default = offline replay, reads only saved files) → `cost/report.md`. `python3 cost/cost_calc.py collect --cold runs/pilot-cold --warm runs/pilot-warm` builds `pilot_records.jsonl`, `pilot_calls.jsonl`, `usage.csv` from run dirs. Never imports provider clients.

## 9. Golden labels / verifier ingest (ChatGPT)

`evals/golden_50.jsonl`: one line per ID: `{"review_id","topic","intent","severity","sentiment","entities","evidence_quote","needs_review","accepted_topic":[…],"accepted_intent":[…],"accepted_severity":[…],"labeller","notes"}`. `evals/gold_benchmark.json` (checker `--gold` format): `{"version":"…","cases":[{"review_id","status":"approved","reviewer","accepted_topic":[…],"accepted_intent":[…],"accepted_severity":[…]}]}`. Infra never reads golden files during a run.

## Change requests

- 2026-10-06 (Hanif): chat roles verify / group / memo use **Claude Haiku 4.5** (`claude-haiku-4-5`, Anthropic API, `ANTHROPIC_API_KEY`) via infra-owned `src/pipeline/anthropic_chat.py`, instead of DeepSeek via OpenRouter. Live runs need Python >= 3.10 + `pip install anthropic`; offline paths stay stdlib-only on 3.9. OpenCode's `chat_client.py` remains a supported alternative (`chat.provider: openrouter`). Verify sample capped at ~2,000 reviews for the full run.
