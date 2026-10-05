# 100-review cost and runtime report

> **No measured pilot yet.** `pilot_calls.jsonl`, `pilot_records.jsonl`, `usage.csv` and `pilot_timing.json` are missing. Run the explicit pilot (cost/README.md), then `collect`. Measured values below are unknown, not zero; the projection uses editable assumptions only.

Generated offline by `python3 cost/cost_calc.py` from saved files only (no API key, no model calls). Spec: [docs/specs/COST_CALCULATOR.md](../docs/specs/COST_CALCULATOR.md). Rates multiplier in force: **1**.

## Inputs

| file | path | sha256 |
|---|---|---|
| assumptions.json | `cost/assumptions.json` | b3ff892ac8373d25… |
| local_compute.csv | `cost/local_compute.csv` | eb46ef302735cf79… |
| pilot_calls.jsonl | `cost/pilot_calls.jsonl` | missing |
| pilot_records.jsonl | `cost/pilot_records.jsonl` | missing |
| pilot_timing.json | `cost/pilot_timing.json` | missing |
| rates.csv | `cost/rates.csv` | 6715f9ce75d498fb… |
| usage.csv | `cost/usage.csv` | missing |

## 1. Measured 100-review pilot — No measured pilot yet

No measured pilot yet. Every measured cell is **unknown** until `collect` runs on real cold/warm run directories.

### 1.1 Input and records

|  | cold | warm |
|---|---|---|
| input file / checksum (sha256) | **unknown** / **unknown** | same input |
| checksum matches manifest | **unknown** | — |
| IDs (expected **unknown**) | **unknown** | same IDs |
| run id | **unknown** | **unknown** |
| completed records | **unknown** | **unknown** |
| failed / quarantined records | **unknown** | **unknown** |
| pending (no record) | **unknown** | **unknown** |
| nonempty texts / empty texts | **unknown** / **unknown** | same |
| unique nonempty texts | **unknown** | same |
| reviews sent to enrich (succeeded calls) | **unknown** | **unknown** |
| result-cache hits (completed, not sent in this run) | **unknown** | **unknown** |
| new enrichment calls | **unknown** | **unknown** |

Sections 1.2–1.5 (per-stage settings, requests and attempts incl. failures/retries/fallbacks/verification, usage and cost by stage, wall clock, stage times, throughput, cost per 1,000 rows and per completed record) appear here after `collect`. Until then they are **unknown**.

## 2. Full-run estimate (editable assumptions, not measured)

Per-unit basis: **assumptions only (no pilot)**. Each stage is extrapolated from its own work count; group and memo are one-time overhead counted once.

### 2.1 Work counts

|  | value |
|---|---|
| rows accounted for | 660,622 |
| nonempty outputs | 660,609 |
| empty-text quarantines | 13 |
| check: nonempty + quarantines = rows | ✓ |
| distinct nonempty texts (exact-text reuse) | 484,189 |
| no-reuse comparison (every nonempty row sent) | 660,609 |

### 2.2 Editable controls (`cost/assumptions.json`)

| control | value |
|---|---|
| budget (USD) | $25.000000 |
| max concurrency (workers) | 2 |
| max fallback fraction (declared cap) | 0.0 |
| verify sample fraction / max items | 0.05 / 2000 |
| retry rate base / conservative | 0.05 / 0.25 |
| measured pilot enrich retry rate (retries / succeeded calls) | **unknown** |
| fallback fraction base / conservative | 0.0 / 0.0 |
| fixed-overhead multiplier base / conservative | 1.0 / 2.0 |
| concurrency efficiency base / conservative | 1.0 / 0.6 |
| output-token cap per call | {"enrich": null, "group": 1500, "memo": 2500, "verify": 600} |
| reasoning tokens included in output | True |

Output-token caps vs observed, and worst-case output cost of one call at the cap:

| stage | declared cap | max observed output tokens | worst-case output cost per call |  |
|---|---|---|---|---|
| enrich | not declared (unknown) | **unknown** | **unknown** (known part $0.000000 + 1 unknown item) |  |
| verify | 600 | **unknown** | **unknown** (known part $0.000000 + 1 unknown item) |  |
| group | 1500 | **unknown** | **unknown** (known part $0.000000 + 1 unknown item) |  |
| memo | 2500 | **unknown** | **unknown** (known part $0.000000 + 1 unknown item) |  |

### 2.3 Per-unit basis

| stage | unit | basis | API cost per unit | input tok/unit | output tok/unit | time |
|---|---|---|---|---|---|---|
| enrich | per review sent | PRE-PILOT ESTIMATE | $0.000021000 | 500 | 0 | **unknown** |
| verify | per review sent | none | **unknown** (known part $0.000000000 + 1 unknown item) | **unknown** | **unknown** | **unknown** |
| group | once per run (fixed) | none | **unknown** (known part $0.000000 + 1 unknown item) | — | — | **unknown** |
| memo | once per run (fixed) | none | **unknown** (known part $0.000000 + 1 unknown item) | — | — | **unknown** |
| fallback | per review routed | none | **unknown** (no fallback calls measured) | — | — | — |
| local overhead | per input row | none | $0 API | — | — | **unknown** |

Enrich unit cost is a **PRE-PILOT ESTIMATE** (src/labelling/PREP.md (Jev cost paragraph): about 500-600 input tokens per review at larger packs; Jev output is free.), not a measurement.

### 2.4 Base case (retry 0.050, fallback 0.0000, fixed ×1.0, 2.00 effective workers)

| stage | work (reuse) | API cost (reuse) | time (reuse) | work (no reuse) | API cost (no reuse) | time (no reuse) |
|---|---|---|---|---|---|---|
| enrich | 484,189 | $10.676367 | **unknown** | 660,609 | $14.566428 | **unknown** |
| fallback | 0 | $0.000000 | 0.00 s | 0 | $0.000000 | 0.00 s |
| verify | 2,000 | **unknown** (known part $0.000000 + 1 unknown item) | **unknown** | 2,000 | **unknown** (known part $0.000000 + 1 unknown item) | **unknown** |
| group | 1 | **unknown** (known part $0.000000 + 1 unknown item) | **unknown** | 1 | **unknown** (known part $0.000000 + 1 unknown item) | **unknown** |
| memo | 1 | **unknown** (known part $0.000000 + 1 unknown item) | **unknown** | 1 | **unknown** (known part $0.000000 + 1 unknown item) | **unknown** |
| local overhead (ingest/rank/export) | 660,622 | $0.000000 | **unknown** | 660,622 | $0.000000 | **unknown** |
| **API total** |  | **unknown** (known part $10.676367 + 3 unknown items) |  |  | **unknown** (known part $14.566428 + 3 unknown items) |  |
| local compute (separate) |  | **unknown** (known part $0.000000 + 1 unknown item) |  |  | **unknown** (known part $0.000000 + 1 unknown item) |  |
| API total if verify used the Batch API (−50.0%, ESTIMATE ONLY, not the measured tier) |  | **unknown** (known part $10.676367 + 3 unknown items) |  |  | **unknown** (known part $14.566428 + 3 unknown items) |  |
| **elapsed time** |  |  | **unknown** |  |  | **unknown** |
| API per 1,000 input rows |  | **unknown** (known part $0.016161 + 3 unknown items) |  |  | **unknown** (known part $0.022050 + 3 unknown items) |  |
| **budget check** |  | ⚠ CANNOT CONFIRM within budget: 3 unknown item(s); known part $10.676367 ≤ $25.000000 |  |  | ⚠ CANNOT CONFIRM within budget: 3 unknown item(s); known part $14.566428 ≤ $25.000000 |  |

### 2.5 Conservative case (retry 0.250, fallback 0.0000, fixed ×2.0, 1.60 effective workers)

| stage | work (reuse) | API cost (reuse) | time (reuse) | work (no reuse) | API cost (no reuse) | time (no reuse) |
|---|---|---|---|---|---|---|
| enrich | 484,189 | $12.709961 | **unknown** | 660,609 | $17.340986 | **unknown** |
| fallback | 0 | $0.000000 | 0.00 s | 0 | $0.000000 | 0.00 s |
| verify | 2,000 | **unknown** (known part $0.000000 + 1 unknown item) | **unknown** | 2,000 | **unknown** (known part $0.000000 + 1 unknown item) | **unknown** |
| group | 1 | **unknown** (known part $0.000000 + 1 unknown item) | **unknown** | 1 | **unknown** (known part $0.000000 + 1 unknown item) | **unknown** |
| memo | 1 | **unknown** (known part $0.000000 + 1 unknown item) | **unknown** | 1 | **unknown** (known part $0.000000 + 1 unknown item) | **unknown** |
| local overhead (ingest/rank/export) | 660,622 | $0.000000 | **unknown** | 660,622 | $0.000000 | **unknown** |
| **API total** |  | **unknown** (known part $12.709961 + 3 unknown items) |  |  | **unknown** (known part $17.340986 + 3 unknown items) |  |
| local compute (separate) |  | **unknown** (known part $0.000000 + 1 unknown item) |  |  | **unknown** (known part $0.000000 + 1 unknown item) |  |
| API total if verify used the Batch API (−50.0%, ESTIMATE ONLY, not the measured tier) |  | **unknown** (known part $12.709961 + 3 unknown items) |  |  | **unknown** (known part $17.340986 + 3 unknown items) |  |
| **elapsed time** |  |  | **unknown** |  |  | **unknown** |
| API per 1,000 input rows |  | **unknown** (known part $0.019239 + 3 unknown items) |  |  | **unknown** (known part $0.026249 + 3 unknown items) |  |
| **budget check** |  | ⚠ CANNOT CONFIRM within budget: 3 unknown item(s); known part $12.709961 ≤ $25.000000 |  |  | ⚠ CANNOT CONFIRM within budget: 3 unknown item(s); known part $17.340986 ≤ $25.000000 |  |

## 3. Rates used (`rates.csv`)

| provider | model | item | unit | price | currency | price per unit (× multiplier) | source | checked on | notes |
|---|---|---|---|---|---|---|---|---|---|
| typesafe | jev-* | input_uncached | token | 42 per 1,000,000,000 | USD | 0.000000042 | https://www.eesel.ai/blog/typesafe-jev-pricing | 2026-10-06 | Jev System One API: input $0.042 per 1M tokens (= $42 per 1B). Official typesafe.ai/pricing returned 404 on 2026-10-06; figure from third-party pricing pages (eesel.ai, layer3labs.io/guides/jev-pricing, updated 2026-09-23) and matches src/labelling/PREP.md. Reconcile with the TypeSafe usage dashboard after the pilot. |
| typesafe | jev-* | input_cached | token | **unknown** (blank) | USD | — | https://docs.typesafe.ai/primitives/choice | not checked | No cached-input rate is documented in the repo. Blank = unknown. Only matters if TypeSafe reports cached_input_tokens. |
| typesafe | jev-* | output | token | 0 per 1,000,000,000 | USD | 0 | https://www.eesel.ai/blog/typesafe-jev-pricing | 2026-10-06 | Jev System One API: no separate output charge (typed decisions, output free). Official typesafe.ai/pricing returned 404 on 2026-10-06; figure from third-party pricing pages (eesel.ai, layer3labs.io/guides/jev-pricing, updated 2026-09-23) and matches src/labelling/PREP.md. Reconcile with the TypeSafe usage dashboard after the pilot. |
| anthropic | claude-haiku-4-5* | input_uncached | token | 1.00 per 1,000,000 | USD | 0.000001 | https://platform.claude.com/docs/en/about-claude/pricing | 2026-10-06 | Claude Haiku 4.5 standard (non-batch) input, $1.00 per 1M tokens. Verified on the official pricing page 2026-10-06. |
| anthropic | claude-haiku-4-5* | input_cached | token | 0.10 per 1,000,000 | USD | 0.0000001 | https://platform.claude.com/docs/en/about-claude/pricing | 2026-10-06 | Prompt-cache read = 0.1x input ($0.10 per 1M). We do not use prompt caching; kept so any reported cached_input_tokens are priced, not dropped. Cache writes are not priced (not used). |
| anthropic | claude-haiku-4-5* | output | token | 5.00 per 1,000,000 | USD | 0.000005 | https://platform.claude.com/docs/en/about-claude/pricing | 2026-10-06 | Claude Haiku 4.5 standard output, $5.00 per 1M tokens (includes any thinking tokens). Anthropic returns no per-response cost, so this calculated cost is the bill. Batch API 50% discount is NOT applied here; it appears only as an estimated scenario. |
| openrouter | deepseek/deepseek-v4.1-flash* | input_uncached | token | **unknown** (blank) | USD | — | https://openrouter.ai/deepseek/deepseek-v4.1-flash | not checked | ALTERNATIVE (not the chosen chat model). TO VERIFY on openrouter.ai/deepseek/deepseek-v4.1-flash before the pilot (price per 1M input tokens). Blank = unknown. |
| openrouter | deepseek/deepseek-v4.1-flash* | input_cached | token | **unknown** (blank) | USD | — | https://openrouter.ai/deepseek/deepseek-v4.1-flash | not checked | ALTERNATIVE (not the chosen chat model). TO VERIFY on openrouter.ai/deepseek/deepseek-v4.1-flash before the pilot (cache-read price per 1M tokens). Blank = unknown. |
| openrouter | deepseek/deepseek-v4.1-flash* | output | token | **unknown** (blank) | USD | — | https://openrouter.ai/deepseek/deepseek-v4.1-flash | not checked | ALTERNATIVE (not the chosen chat model). TO VERIFY on openrouter.ai/deepseek/deepseek-v4.1-flash before the pilot (price per 1M output tokens, reasoning included). Blank = unknown. |
| * | * | uncertain_charge | usd | 1 per 1 | USD | 1 | — | not checked | Pass-through for timeouts flagged uncertain_charge. usage.csv leaves billed_units blank (= unknown). After reconciling with the provider dashboard, enter the charged USD amount (0 if none) in billed_units. |

⚠ 4 rate(s) are blank and therefore **unknown**: typesafe jev-* input_cached; openrouter deepseek/deepseek-v4.1-flash* input_uncached; openrouter deepseek/deepseek-v4.1-flash* input_cached; openrouter deepseek/deepseek-v4.1-flash* output. Fill them from the source link (with `checked_on`) before relying on totals.

## 4. Formulas and evidence

- `price_per_unit = price / per` (a per-million price is divided by 1,000,000 first).
- `item_cost = billed_units × price_per_unit × rates_multiplier`; `total = Σ item_cost`. Items per call are mutually exclusive: `input_uncached = input_tokens − cached_input_tokens`, `input_cached`, `output` (reasoning already inside output is not added again), optional `request`/`classification`, and `uncertain_charge` (USD pass-through, blank until reconciled).
- Any blank price or unmeasured unit makes that item **unknown**; totals show the known part plus the count of unknown items.
- Every `usage.csv` row maps to one `pilot_calls.jsonl` line by `(run, request_id)`.
- Projection per stage: `cost = work × unit_cost × (1 + retry_rate)`; verify work = `ceil(verify_sample_fraction × work)`; fallback work = `ceil(fallback_fraction × work)` (≤ max_fallback_fraction); group/memo = measured one-time cost × fixed multiplier × (1 + retry). Time = `work × (1 + retry) / (per-worker throughput × (1 + (max_concurrency − 1) × efficiency))` + one-time stage time + local overhead per row × rows.
- API spend is separate from local compute; local compute = hours × watts / 1000 × USD/kWh (+ fixed), unknown when any input is blank.
- The measured section depends only on the evidence files and rates; projection assumptions never change it.
- The first 100 reviews give an initial estimate only. Refresh after 500 and 10,000 reviews before the full run.

