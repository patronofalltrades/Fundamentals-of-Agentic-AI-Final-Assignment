# Run configs

`run_pipeline.py <csv> --config <file> --out runs/<name> [--dry-run] ...` reads one JSON config.
`run_labelling.py` is the same command with `--stages ingest,enrich`.

| File | Use |
|---|---|
| `dry_run.json` | Offline runs with `--dry-run`. No keys, no network, no spend. The enrich client is OpenCode's `MockClient` (model `mock`). `label_config` becomes `mock:<label_config>`. Chat roles use `pipeline.clients.MockChat`. |
| `pilot_cost_100.json` | The real 100-review pilot (`cost_100.csv`). Jev through TypeSafe for enrich. Claude Haiku 4.5 through the Anthropic API for verify/group/memo. 1 worker, $1.00 cap, at most 50 reviews per request. |

## Commands

```sh
DATA="$HOME/Desktop/Fundamentals of Agentic AI - Final Assignment - Spotify/Final Assignment - Spotify Reviews Dataset"

# offline
python3 run_pipeline.py "$DATA/cost_100.csv" --config configs/dry_run.json --out runs/dry-100 --dry-run
# interruption demo: stop after 3 batches, then resume
python3 run_pipeline.py "$DATA/checkpoint_500.csv" --config configs/dry_run.json --out runs/dry-500 --dry-run --stages ingest,enrich --max-batches 3
python3 run_pipeline.py "$DATA/checkpoint_500.csv" --config configs/dry_run.json --out runs/dry-500 --dry-run --stages ingest,enrich

# live pilot (costs money; needs keys)
.venv/bin/python run_pipeline.py "$DATA/cost_100.csv" --config configs/pilot_cost_100.json --out runs/pilot-cold
.venv/bin/python run_pipeline.py "$DATA/cost_100.csv" --config configs/pilot_cost_100.json --out runs/pilot-warm --warm-from runs/pilot-cold
```

`--warm-from <run>` seeds a new, empty run directory with the completed records of another run that used the same `label_config`. A different `label_config` is refused. The warm invocation has phase `resume` and makes zero enrich calls. `run_config.json` records `warm_from: {path, records_copied, source_label_config}`.

## Python and keys

- Offline runs (dry run, tests, export, cost replay) use the system `python3` (3.9+) and the standard library only.
- Live runs need Python 3.10 or later and the Anthropic SDK for the chat roles. Example: `uv venv --python 3.12 .venv && uv pip install anthropic`. `.venv/` is git-ignored.
- `run_pipeline.py` loads a git-ignored `.env` at the repo root before it builds clients. The format is `KEY=value` lines. Comments and blank lines are ignored and optional quotes are removed. Variables that are already set in the environment are not overridden. Only the key names are logged, never the values. Keys: `TYPESAFE_API_KEY` (enrich), `ANTHROPIC_API_KEY` (chat roles), and optionally `ANTHROPIC_WORKSPACE_ID` and `OPENROUTER_API_KEY` (alternative chat provider).
- **Mock guard:** without `--dry-run`, a missing enrich key or chat key stops the run before any work (exit 4). A dry run always uses the mocks, even when keys are set.

## Keys in a config

| Key | Meaning |
|---|---|
| `label_config` | Model + prompt + schema version string. It is written on every record and every enrich call. A change means new work (no cache reuse). |
| `full_run` | `true` for full-corpus configs. `--limit` is refused when it is `true`. |
| `client` | Enrich client for `labelling.model_client.create_client`: `provider` (`typesafe`, `openrouter` or `beatapi`), `model`, `endpoint`, `api_key_env`, `timeout_seconds`, `needs_review_threshold`. |
| `chat` | Chat roles: `provider` (`anthropic` is the default; `openrouter` uses OpenCode's `labelling.chat_client`), `model` (`claude-haiku-4-5`), `api_key_env`, `timeout_seconds`, `temperature`, `effort` (`none`: no extended thinking), `max_output_tokens` per role (for reference), `alternatives` (documentation only). |
| `batching.max_reviews_per_request` | At most 50 (hard cap). |
| `batching.size_by_tokens`, `token_budget` | Uses the client module's `max_batch_by_tokens` to make batches smaller so the request fits the context (32k for Jev). |
| `result_cache.enabled` | Exact-text reuse with `cache_source_id`. The first ID in file order for a text is sent, and the others copy its labels. |
| `limits.workers` | Worker threads (`--workers` overrides). They share one rate limiter and one spend ledger. Start with 1. |
| `limits.spend_cap_usd` | Stop admitting work when `spent + reserved + next > cap`. Exit code 2. |
| `limits.requests_per_minute`, `tokens_per_minute` | Shared token-bucket limits (`null` = off). |
| `limits.max_transient_attempts` | Attempts per request for 429/5xx/timeout errors. Backoff is exponential with full jitter and honours `retry_after`. |
| `limits.invalid_attempts` | Attempts on invalid output before the batch is split in half (2 = one retry). |
| `limits.missing_retry_rounds` | Re-send rounds for IDs that were missing or invalid in an otherwise good response. After that they are quarantined. |
| `limits.backoff_base_seconds`, `backoff_max_seconds` | Backoff shape. |
| `limits.max_consecutive_failed_batches` | Stop the invocation (exit 6) after this many batches in a row exhaust their transient retries. |
| `limits.retry_quarantined` | Re-send previously quarantined (non-empty) IDs on the next invocation. |
| `limits.est_output_tokens_per_review`, `reserve_usd_per_enrich_request` | Worst-case reservation per enrich request. If the cost is unknown (no `cost_usd` from the provider and no rates), the reservation is charged as an "unpriced" estimate. It never counts as zero. |
| `limits.progress_every_batches` | Progress line to stderr every N batches (0 = off). |
| `rates.<role>` | `input_per_mtok`, `cached_input_per_mtok`, `output_per_mtok`, `per_request` in USD. These are for the spend ledger only. `cost/rates.csv` is the source for the calculator. |
| `verify`, `group`, `memo` | Settings for the downstream stages (`sample_fraction`, `min_items`, `max_items`, `max_tokens`, ...). `verify.max_items` is 2000 for full-run configs. The pilot verifies a declared sample of at most 100. Default role `max_tokens`: verify 600, group 1500, memo 2500. |

## Run directory outputs

See `docs/INTERFACES.md` section 4. Each invocation appends one line to `invocations.jsonl` with `wall_seconds`, `stage_seconds` (`ingest`, `enrich`, `verify`, `group`, `rank`, `memo`; `null` if the stage did not run), `stop_reason` and counts. It also writes `checkpoints/<invocation_id>-start.json` and `-end.json`.

Exit codes:

| Code | Meaning |
|---|---|
| 0 | Done, including a `--max-batches` stop |
| 2 | Budget stop |
| 3 | Model client error (for example 402, out of credits) |
| 4 | Configuration error or mock guard |
| 5 | Stage module missing or failed |
| 6 | Repeated transient failures |
| 130 | Interrupted (SIGINT) |
