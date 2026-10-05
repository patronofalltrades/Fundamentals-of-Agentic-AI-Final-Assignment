# cost/ — 100-review cost and runtime calculator

Offline calculator for [docs/specs/COST_CALCULATOR.md](../docs/specs/COST_CALCULATOR.md). It uses the Python 3.9+ standard library only. Importing or running `cost_calc.py` never makes network or provider calls, and it does not import `src/labelling/`.

## Offline replay (default, no API key)

```bash
python3 cost/cost_calc.py                               # reads saved files in cost/, writes cost/report.md
python3 cost/cost_calc.py replay --rates-multiplier 2   # doubles every API price: API subtotal doubles; time and local compute do not change
python3 cost/cost_calc.py replay --set budget_usd=10 --set projection.distinct_nonempty_texts=500000   # edit assumptions on the command line
python3 cost/cost_calc.py replay --csv "<DATASET>/cost_100.csv"   # re-check the checksum (manifest.json) and the 100 IDs
python3 cost/cost_calc.py replay --source cost/fixtures            # SYNTHETIC example (tests only; labelled NOT measured)
```

Before the pilot exists, the default command still runs. The report then says **"No measured pilot yet"**, shows all measured cells as **unknown**, and shows the full-run framework. The enrich line uses a labelled PRE-PILOT ESTIMATE.

## Explicit pilot execution (paid calls, run only after Hanif approves the budget)

```bash
# 1. cold run: empty result cache, 1 worker
python3 run_pipeline.py "<DATASET>/cost_100.csv" --config configs/pilot_cost_100.json --out runs/pilot-cold
# 2. warm run: same settings, reuse the cold result cache (must show zero new enrich calls)
python3 run_pipeline.py "<DATASET>/cost_100.csv" --config configs/pilot_cost_100.json --out runs/pilot-warm --warm-from runs/pilot-cold
# 3. build the evidence files (no calls)
python3 cost/cost_calc.py collect --cold runs/pilot-cold --warm runs/pilot-warm --csv "<DATASET>/cost_100.csv"
# 4. offline replay
python3 cost/cost_calc.py
```

`<DATASET>` = `~/Desktop/Fundamentals of Agentic AI - Final Assignment - Spotify/Final Assignment - Spotify Reviews Dataset`. If you leave out `--csv`, `collect` uses the run config's `input_csv`, then `$A5_DATASET_DIR/cost_100.csv`.

> **Note:** the `--warm-from` flag is still pending in the harness (`run_pipeline.py`, owned by infra). Confirm it exists before step 2.

`collect` refuses to write if the CSV checksum differs from `docs/specs/manifest.json`, if the CSV does not have exactly 100 unique IDs, if a run has IDs not in the CSV, or if a record's `source_sha256` does not match the row hash. A run whose config has `dry_run: true` (mock client) is labelled DRY-RUN, never measured.

## Files

| file | kind | what it is |
|---|---|---|
| `cost_calc.py` | code | `replay` (default) and `collect` commands. Formulas are in its docstring and in report section 4. |
| `rates.csv` | editable input | One row per (provider, model pattern, billing item): `unit, price, currency, per, source_url, checked_on, notes`. A blank price = **unknown**. |
| `assumptions.json` | editable input | Budget, output-token caps, max concurrency, max fallback fraction, verify sample, retry/fallback rates (base and conservative), fixed-overhead multiplier, Batch API estimate, projected counts (660,622 / 660,609 / 13 / 484,189). Documented in its `_doc` block. |
| `local_compute.csv` | editable input | Host machine, hours (blank = wall clock), watts, USD/kWh. Blank values make local compute **unknown**, never 0. It is reported separately from API spend. |
| `pilot_records.jsonl` | evidence (from `collect`) | One line per pilot ID, in CSV order, in grading-record shape with `source_sha256`. It adds `pilot_status` (cold/warm). It is separate from `grading/records.jsonl`. |
| `pilot_calls.jsonl` | evidence (from `collect`) | Every attempt from both runs (failures, retries and timeouts included). Each line has `run` (cold/warm) and `run_id` added, keeps all provider fields, and has key-like fields and values removed. |
| `usage.csv` | evidence (from `collect`) | One row per billed item per call: `request_id, run, role, provider, model, item, billed_units, unit, note`. Each row maps to a call by `(run, request_id)`. |
| `pilot_timing.json` | evidence (from `collect`) | Provenance (checksum, ID check, data source), and for each run: wall seconds from `invocations.jsonl`, stage durations, record counts, cache hits and declared settings. |
| `report.md` | output | The dashboard: measured cold vs warm, full-run base and conservative cases (reuse vs no reuse), controls, warnings, rates and formulas. |
| `fixtures/` | tests only | A **SYNTHETIC** 10-row pilot (`make_fixtures.py` regenerates it). It includes a 429 that is retried, a timeout flagged `uncertain_charge`, a cache hit, an empty-text quarantine, and a warm run with zero enrich calls. Replaying this folder always prints a SYNTHETIC banner. |

## Billing items (mutually exclusive per call)

- `input_uncached` = `input_tokens − cached_input_tokens`. Call logs report `input_tokens` as **total** input, so the calculator subtracts cached input before it applies the uncached rate.
- `input_cached` = `cached_input_tokens` (a row is written only when the provider reports it).
- `output` = `output_tokens`. Reasoning/thinking tokens are already inside output, so they are not billed again. Set `reasoning_tokens_included_in_output: false` to bill them as a separate `reasoning` item.
- `request` and `classification` rows appear only if `rates.csv` defines those items for the model.
- `uncertain_charge` is written for a timeout with an unknown outcome. Its `billed_units` stays blank (unknown) until you reconcile it with the provider dashboard. Then enter the USD amount (0 if there was no charge).

`item_cost = billed_units × price / per × rates_multiplier`, and `total = Σ item_cost`. If any item is unknown, the total shows as **unknown** with the known part beside it. When a provider reports `cost_usd`, the report shows it beside the calculated cost as a reconciliation column.

## Providers and rates (see `rates.csv`)

| role | provider / model | rate status |
|---|---|---|
| enrich | TypeSafe Jev (`jev-*`, served e.g. `jev-1.13.0`) | Input $42 per 1B tokens. Output $0. Source: `src/labelling/PREP.md` / `HANDOFF.md` (2026-10-05). **Re-check before the pilot.** There is no documented cached-input rate (blank = unknown). |
| verify, group, memo | Anthropic Claude Haiku 4.5 (`claude-haiku-4-5*`) | Input $1.00 per 1M tokens. Output $5.00 per 1M tokens. Cache read $0.10 per 1M (0.1× input; prompt caching is not used, but any reported cached tokens are priced). Source: [Anthropic pricing](https://platform.claude.com/docs/en/about-claude/pricing), from the model table cached 2026-09-25, supplied 2026-10-06. **Re-check before the pilot.** Anthropic returns no per-response cost (`cost_usd` = null), so the calculated cost is the bill. |
| alternative (not chosen) | OpenRouter DeepSeek V4.1 Flash | Prices are blank (TO VERIFY on openrouter.ai). They are only used if a call log names this model. |

The Anthropic **Batch API** discount (50%) is never applied to the measured bill. It appears only as a separate "ESTIMATE ONLY" line in each projection scenario, for the roles listed in `assumptions.json` → `batch_api_estimate.roles`.

## Projection method (report section 2)

Each stage is extrapolated from its own work count:

- enrich: distinct texts (reuse) or nonempty rows (no reuse) × measured cost per review × (1 + retry rate).
- verify: `min(ceil(sample_fraction × work), max_items)`. The defaults are 0.05 and 2000.
- fallback: capped by `max_fallback_fraction`. Its cost is unknown unless fallback calls were measured.
- group and memo: the measured one-time cost, counted **once** (× fixed multiplier × (1 + retry)). It is never multiplied by the row count.

Time = per-worker throughput from the pilot (failed attempts included) scaled by effective workers, plus one-time stage time, plus local overhead per row. A ⚠ warning appears when a scenario exceeds the budget, or when it cannot be confirmed because items are unknown.

## Tests

```bash
python3 -m unittest tests.test_cost_calc
```

The tests cover: per-million conversion, cached-input subtraction, no double-counted reasoning, unknown propagation, the rate-doubling invariant (with the multiplier and with an edited rates.csv), changing projected counts without changing the measured results, group/memo counted once, budget/cap/fallback warnings, `collect` on the fixtures (byte-identical output), checksum and ID mismatches, key stripping, DRY-RUN/SYNTHETIC labelling, and no network access during import + replay.
