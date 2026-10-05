# Claude Opus — Infrastructure Brief (Assignment 5)

You are the **infrastructure engineer** on a 3-agent team building the "Final Assignment — Multi Agent Large Data Processing Pipeline" (Spotify reviews). This brief defines your scope, the contracts you must hand to the other two agents, and the constraints you must respect. **Read the supplied spec files before writing any code.**

## Team & division of labor

- **Claude Opus (you): Infrastructure.** Pipeline skeleton, prepare/ingestion, state & resume, batching harness, validation, grouping, ranking, claims, memo scaffolding, cost calculator, grading exporter, checker compliance, repo hygiene.
- **OpenCode: Labelling.** Implements the model client and runs all enrichment/classification stages (`cost_100` → `checkpoint_500` → `analysis_10000` → full corpus). Chooses providers/models within the shared rubric.
- **ChatGPT: Evals.** Human golden-50 labels, independent verification role, error analysis, overlap disclosure, adversarial/injection tests.

## Do NOT do

- **No labelling runs, no model calls, no API spend.** Everything you build must run offline with zero credentials.
- No golden labels, no eval analysis, no label-semantics decisions beyond encoding the shared rubric into schema and prompt templates.

## Assignment facts (already verified)

- Full corpus: `spotify_reviews_18months.csv` — 660,622 IDs, 660,609 nonempty texts, 13 empty texts to quarantine with reason `empty_review_text`, 484,189 distinct nonempty exact texts, 176,420 repeated nonempty texts after the first, 159,701 missing `app_version`.
- Full file SHA-256 `1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6`, 97,400,616 bytes.
- Deadline: **Oct 13, 2026 11:59pm PT**. Submission = this public repo. Full-run scope per the grading contract.

## Spec files — read these first (authoritative)

- `~/Desktop/Fundamentals of Agentic AI - Final Assignment - Spotify/Final Assignment - Spotify Reviews Dataset/GRADING_CONTRACT.md`
- `.../COST_CALCULATOR.md`
- `.../README.md` and `manifest.json`
- `.../check_submission.py` (the zero-API grader audit — you MUST be byte-compatible with its expectations)

Vendor the spec files into this repo under `docs/specs/` and `check_submission.py` at repo root so all three agents share one source of truth. Add a passing self-check report for the grader against the real CSV (read-only, no model calls).

## Deliverables

### 1. Repo hygiene & setup
- `requirements.txt` / `pyproject.toml` — standard library preferred, minimal deps; offline replay must need no provider SDKs.
- `.env.example` (blank credentials), `.gitignore`.

### 2. Pipeline package (`src/`) — all modules offline-testable
- `prepare`: streaming CSV parse; `row_sha` reproducing `check_submission.py` `canonical()`/`row_sha()` exactly (SHA-256 of compact UTF-8 JSON, `ensure_ascii=False, separators=(",",":"), sort_keys=True`, of the six fields in order `review_id, review_text, review_rating, review_likes, app_version, review_timestamp`, no normalization); full-file profile matching checker `profile()` (counts, dup IDs, empty texts, missing app_version, by-month, by-rating, first/last timestamp); exact-text index; pending-work queue.
- `state`: atomic per-ID status store (upsert), checkpoint save/load (`completed_ids`), resume that never re-calls completed IDs under unchanged config.
- `spend`: shared rate limiter + spend ledger, per-stage reservations, budget cap (stop admitting work when spent + reserved + next > cap), bounded retries with backoff/jitter, timeout reconciliation flags.
- `enrich`: batching ≤50 reviews/request; call logging in `calls.jsonl` format; outcome handling (`succeeded`/`failed`); retry policy; fallback-fraction cap; exact-text cache with `cache_source_id` (direct original only, identical text + identical label fields + `classification_input_fields == ["review_text"]`); per-batch validation that every returned ID was in the request.
- **Model client interface (contract for OpenCode):** `src/labelling/model_client.py` with a typed `classify_batch(reviews, label_config) -> list[Record]`. You build the harness plus a mock/dry-run client so offline tests run; OpenCode fills in the real provider client.
- `verify`: interface for the eval verifier (ChatGPT) — re-labels original text before seeing the first prediction; saves a disagreement report.
- `group`: code computes membership, stable issue IDs, rejects foreign/duplicate pairs, single-issue default.
- `rank`: deterministic `severity_sum`, `priority_score = severity_sum`, `mean_severity` to 6 decimals with decimal half-up rounding, sort desc score then asc issue_id, rank from 1; reproducible from saved records with no model calls.
- `claims`: export `claim_id, issue_id, metric, value` for the four supported metrics.
- `memo`: scaffolding + interface for the memo role reading saved aggregates (offline stub producing a placeholder).
- `grading`: exporter writing the exact grading files below.

### 3. Grading export (`grading/`) — exact format from GRADING_CONTRACT.md
- `run.json`: exactly `{"version":"a5-audit-v1","analysis_count":660622,"analysis_sha256":"1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6","classification_input_fields":["review_text"],"allow_multi_issue":false}`.
- `ingestion.json`: output of `check_submission.py profile`.
- `records.jsonl`: one line per ID. Completed: `{review_id, source_sha256, status:"completed", topic, intent, sentiment∈[-1,1], severity∈1..5 int, entities[nonempty str], evidence_quote (exact source substring), needs_review:bool, label_config}`. Quarantined: `{review_id, source_sha256, status:"quarantined", reason}`.
- `membership.csv` `issue_id,review_id`; `ranking.csv` `rank,issue_id,complaint_count,severity_sum,mean_severity,priority_score`; `claims.csv` `claim_id,issue_id,metric,value`.
- `calls.jsonl`: `{request_id, role: enrich|verify|group|memo, review_ids:[...], model, phase: initial|resume, outcome: succeeded|failed, label_config, input_tokens, output_tokens}`; enrichment ids 1..50, unique, must name the same `label_config` as completed records.
- `checkpoint_before.json` / `checkpoint_after.json`: `{"completed_ids":[...]}` (before nonempty, after strictly larger).
- A single command produces all of these from saved state — no manual chat pasting.

### 4. Cost calculator (`cost/`)
- Runnable offline calculator; opening/importing it must never trigger paid calls.
- Reads real `pilot_calls.jsonl`, `usage.csv`, `rates.csv` (editable, dated, unit-accurate, source links); computes `billed_units × price_per_unit` per mutually exclusive item; subtracts cached input before uncached rate; no double-counted reasoning tokens.
- Displays measured cold vs warm pilot (cost, wall time, throughput, cache hits, failures) AND projected full run (base + conservative cases) for 660,609 rows with the 484,189 distinct-text reuse comparison; fixed overhead once; stage-specific verify/fallback work; editable budget / output-token cap / concurrency / max fallback fraction; warning when a scenario exceeds budget.
- With fixed usage, doubling API rates must double API subtotal and leave measured time + local costs unchanged.
- `README.md` with separate offline-replay and explicit pilot-execution commands; `report.md` dashboard.

### 5. Interfaces for the other agents — `docs/INTERFACES.md`
- Exact `model_client.py` contract OpenCode implements (signatures, Record/error types, `label_config` string convention, usage recording).
- Verifier interface ChatGPT uses + golden-label ingest format.
- CLI entrypoints (`run_labelling.py <csv> --config`, `export_grading.py`, `cost_calc.py --replay`, etc.).
- Directory layout partitioning the work: `src/` (you), `src/labelling/` (OpenCode), `evals/` (ChatGPT), `grading/`, `cost/`.

## Working style
- Branch `claude-infra`; commit atomically with clear messages; push so other agents can see your interfaces early.
- Do not merge to main yourself; leave branches/PRs for the coordinator (Hanif).
- Self-check: run `check_submission.py profile/reference/check` against the real CSV from the Desktop dataset folder and commit a passing self-check report.
- No API keys in the repo; `.env.example` only.
