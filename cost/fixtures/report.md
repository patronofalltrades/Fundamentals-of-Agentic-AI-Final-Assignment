# 100-review cost and runtime report

> ⚠ **SYNTHETIC FIXTURE DATA — NOT A MEASURED PILOT.** Every token count, duration and cost below is invented test data from `cost/fixtures/`. Do not cite it as evidence.

Generated offline by `python3 cost/cost_calc.py` from saved files only (no API key, no model calls). Spec: [docs/specs/COST_CALCULATOR.md](../docs/specs/COST_CALCULATOR.md). Rates multiplier in force: **1**.

## Inputs

| file | path | sha256 |
|---|---|---|
| assumptions.json | `cost/assumptions.json` | b3ff892ac8373d25… |
| local_compute.csv | `cost/local_compute.csv` | eb46ef302735cf79… |
| pilot_calls.jsonl | `cost/fixtures/pilot_calls.jsonl` | f0e51f1b41bb6ab9… |
| pilot_records.jsonl | `cost/fixtures/pilot_records.jsonl` | 53e09fc662edeb14… |
| pilot_timing.json | `cost/fixtures/pilot_timing.json` | 08cc04f991ec1013… |
| rates.csv | `cost/rates.csv` | 0a65802d36a9884b… |
| usage.csv | `cost/fixtures/usage.csv` | ec8f4cc19ec2fbcd… |

## 1. SYNTHETIC pilot fixture (cold vs warm) — NOT measured

### 1.1 Input and records

|  | cold | warm |
|---|---|---|
| input file / checksum (sha256) | cost_10_synthetic.csv / `ace848ed66b9bdd7078b3d8b63e6dd58daf15f8c9f87b2ceb4bca777f152f66c` | same input |
| checksum matches manifest | ✓ cost/fixtures/manifest_synthetic.json | — |
| IDs (expected 10) | 10 ✓ match CSV | same IDs |
| run id | syn-cold | syn-warm |
| completed records | 9 | 9 |
| failed / quarantined records | 1 | 1 |
| pending (no record) | 0 | 0 |
| nonempty texts / empty texts | 9 / 1 | same |
| unique nonempty texts | 8 | same |
| reviews sent to enrich (succeeded calls) | 8 | 0 |
| result-cache hits (completed, not sent in this run) | 1 | 9 |
| new enrichment calls | 4 | 0 ✓ zero |

`pilot_records.jsonl`: 10 lines; 0 quarantined for a reason other than empty text (fix before scaling).

### 1.2 Per-stage settings (declared in run_config.json; observed in calls)

| stage | run | provider | exact model ID | effort | prompt / schema version | label_config | reviews per request | workers |
|---|---|---|---|---|---|---|---|---|
| enrich | cold | typesafe | jev-1.13.0 | **unknown** | v1 / a5-v1 | typesafe/jev-latest:prompt-v1:schema-a5-v1 | 4–4 (mean 4.0) (declared max 50) | 1 |
| enrich | warm | declared: typesafe | declared: jev-latest | **unknown** | v1 / a5-v1 | declared: typesafe/jev-latest:prompt-v1:schema-a5-v1 | no calls (declared max 50) | 1 |
| verify | cold | anthropic | claude-haiku-4-5 | declared: none | draft-1 / **unknown** | — | 2–2 (mean 2.0) (declared max **unknown**) | 1 |
| verify | warm | declared: anthropic | declared: claude-haiku-4-5 | declared: none | draft-1 / **unknown** | — | no calls (declared max **unknown**) | 1 |
| group | cold | anthropic | claude-haiku-4-5 | declared: none | draft-1 / **unknown** | — | — (saved aggregate pack) | 1 |
| group | warm | declared: anthropic | declared: claude-haiku-4-5 | declared: none | draft-1 / **unknown** | — | — (saved aggregate pack) | 1 |
| memo | cold | anthropic | claude-haiku-4-5 | declared: none | draft-1 / **unknown** | — | — (saved aggregate pack) | 1 |
| memo | warm | anthropic | claude-haiku-4-5 | declared: none | draft-1 / **unknown** | — | — (saved aggregate pack) | 1 |

### 1.3 Requests and attempts

| stage | run | attempts | succeeded | failed | retries (attempt>1) | fallbacks | uncertain charge (timeouts) | reviews in succeeded calls |
|---|---|---|---|---|---|---|---|---|
| enrich | cold | 4 | 2 | 2 | 2 | 0 | 1 | 8 |
| enrich | warm | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| verify | cold | 1 | 1 | 0 | 0 | 0 | 0 | 2 |
| verify | warm | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| group | cold | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| group | warm | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| memo | cold | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| memo | warm | 1 | 1 | 0 | 0 | 0 | 0 | 0 |

Verification calls are the `verify` rows. Failed attempts are listed with their error in `pilot_calls.jsonl`.

⚠ Uncertain charges (timeouts): `syn-req-03` (cold, enrich). Their cost stays **unknown** until reconciled: enter the dashboard USD amount in `usage.csv` (item `uncertain_charge`).

### 1.4 Usage and cost by stage (API)

| stage | run | input uncached (tokens) | input cached (tokens) | output (tokens) | reasoning (tokens) | calculated cost | provider-reported cost_usd | calculated − reported |
|---|---|---|---|---|---|---|---|---|
| enrich | cold | 4,700 | not reported | 780 | not reported | **unknown** (known part $0.000197 + 1 unknown item) | **unknown** (not reported) | — |
| enrich | warm | — | not reported | — | — | $0.000000 | — | — |
| verify | cold | 600 | 300 | 120 | 40 (in output) | $0.001230 | none (Anthropic returns no per-call cost; calculated = bill) | — |
| verify | warm | — | not reported | — | — | $0.000000 | — | — |
| group | cold | 1,500 | 0 | 200 | 0 (in output) | $0.002500 | none (Anthropic returns no per-call cost; calculated = bill) | — |
| group | warm | — | not reported | — | — | $0.000000 | — | — |
| memo | cold | 2,500 | 0 | 600 | 0 (in output) | $0.005500 | none (Anthropic returns no per-call cost; calculated = bill) | — |
| memo | warm | 452 | 2,048 | 590 | 0 (in output) | $0.003607 | none (Anthropic returns no per-call cost; calculated = bill) | — |

Unknown items (not counted as zero):

- billed units not measured (uncertain_charge)

### 1.5 Totals, time and throughput

|  | cold | warm (incremental) |
|---|---|---|
| API spend (all stages) | **unknown** (known part $0.009427 + 1 unknown item) | $0.003607 |
| local compute (separate, from local_compute.csv) | **unknown** (known part $0.000000 + 1 unknown item) | **unknown** (known part $0.000000 + 1 unknown item) |
| end-to-end wall clock (invocations.jsonl) | 87.50 s | 3.40 s |
| enrich time (request durations summed / first start→last end) | 68.40 s summed / 71.00 s span | 0 calls |
| verify time (request durations summed / first start→last end) | 2.00 s summed / 2.00 s span | 0 calls |
| group time (request durations summed / first start→last end) | 3.00 s summed / 3.00 s span | 0 calls |
| memo time (request durations summed / first start→last end) | 6.00 s summed / 6.00 s span | 2.00 s summed / 2.00 s span |
| throughput (input rows / wall second) | 0.114 | 2.941 |
| API cost per 1,000 input rows | **unknown** (known part $0.942740 + 1 unknown item) | $0.360680 |
| API cost per completed record | **unknown** (known part $0.001047 + 1 unknown item) | $0.000401 |
| pilot budget | $1.000000 | cold + warm: **unknown** (known part $0.013034 + 1 unknown item) |

Summed request durations can exceed wall clock when calls overlap; wall clock comes from `invocations.jsonl`.

## 2. Full-run estimate (editable assumptions, not measured)

Per-unit basis: **SYNTHETIC fixture (illustration only)**. Each stage is extrapolated from its own work count; group and memo are one-time overhead counted once.

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
| measured pilot enrich retry rate (retries / succeeded calls) | 1.000 |
| fallback fraction base / conservative | 0.0 / 0.0 |
| fixed-overhead multiplier base / conservative | 1.0 / 2.0 |
| concurrency efficiency base / conservative | 1.0 / 0.6 |
| output-token cap per call | {"enrich": null, "group": 1500, "memo": 2500, "verify": 600} |
| reasoning tokens included in output | True |

Output-token caps vs observed, and worst-case output cost of one call at the cap:

| stage | declared cap | max observed output tokens | worst-case output cost per call |  |
|---|---|---|---|---|
| enrich | not declared (unknown) | 400 | **unknown** (known part $0.000000 + 1 unknown item) |  |
| verify | 600 | 120 | $0.003000 |  |
| group | 1500 | 200 | $0.007500 |  |
| memo | 2500 | 600 | $0.012500 |  |

### 2.3 Per-unit basis

| stage | unit | basis | API cost per unit | input tok/unit | output tok/unit | time |
|---|---|---|---|---|---|---|
| enrich | per review sent | pilot | $0.000024675 | 587.5 | 97.5 | 0.117 reviews/s per worker |
| verify | per review sent | pilot | $0.000615000 | 450.0 | 60.0 | 1.000 reviews/s per worker |
| group | once per run (fixed) | pilot | $0.002500 | — | — | 3.00 s |
| memo | once per run (fixed) | pilot | $0.005500 | — | — | 6.00 s |
| fallback | per review routed | none | **unknown** (no fallback calls measured) | — | — | — |
| local overhead | per input row | pilot | $0 API | — | — | 810.000 ms/row (wall − summed call time, ÷ pilot rows; linear, upper bound) |

### 2.4 Base case (retry 0.050, fallback 0.0000, fixed ×1.0, 2.00 effective workers)

| stage | work (reuse) | API cost (reuse) | time (reuse) | work (no reuse) | API cost (no reuse) | time (no reuse) |
|---|---|---|---|---|---|---|
| enrich | 484,189 | $12.544732 | 2,173,403.4 s (603.72 h) | 660,609 | $17.115553 | 2,965,308.6 s (823.70 h) |
| fallback | 0 | $0.000000 | 0.00 s | 0 | $0.000000 | 0.00 s |
| verify | 2,000 | $1.291500 | 1,050.00 s | 2,000 | $1.291500 | 1,050.00 s |
| group | 1 | $0.002625 | 3.15 s | 1 | $0.002625 | 3.15 s |
| memo | 1 | $0.005775 | 6.30 s | 1 | $0.005775 | 6.30 s |
| local overhead (ingest/rank/export) | 660,622 | $0.000000 | 535,103.8 s (148.64 h) | 660,622 | $0.000000 | 535,103.8 s (148.64 h) |
| **API total** |  | $13.844632 |  |  | $18.415453 |  |
| local compute (separate) |  | **unknown** (known part $0.000000 + 1 unknown item) |  |  | **unknown** (known part $0.000000 + 1 unknown item) |  |
| API total if verify used the Batch API (−50.0%, ESTIMATE ONLY, not the measured tier) |  | $13.198882 |  |  | $17.769703 |  |
| **elapsed time** |  |  | 2,709,566.6 s (752.66 h) |  |  | 3,501,471.9 s (972.63 h) |
| API per 1,000 input rows |  | $0.020957 |  |  | $0.027876 |  |
| **budget check** |  | within budget ($13.844632 ≤ $25.000000) |  |  | within budget ($18.415453 ≤ $25.000000) |  |

### 2.5 Conservative case (retry 0.250, fallback 0.0000, fixed ×2.0, 1.60 effective workers)

| stage | work (reuse) | API cost (reuse) | time (reuse) | work (no reuse) | API cost (no reuse) | time (no reuse) |
|---|---|---|---|---|---|---|
| enrich | 484,189 | $14.934204 | 3,234,231.2 s (898.40 h) | 660,609 | $20.375659 | 4,412,661.7 s (1225.74 h) |
| fallback | 0 | $0.000000 | 0.00 s | 0 | $0.000000 | 0.00 s |
| verify | 2,000 | $1.537500 | 1,562.50 s | 2,000 | $1.537500 | 1,562.50 s |
| group | 1 | $0.006250 | 7.50 s | 1 | $0.006250 | 7.50 s |
| memo | 1 | $0.013750 | 15.00 s | 1 | $0.013750 | 15.00 s |
| local overhead (ingest/rank/export) | 660,622 | $0.000000 | 535,103.8 s (148.64 h) | 660,622 | $0.000000 | 535,103.8 s (148.64 h) |
| **API total** |  | $16.491704 |  |  | $21.933159 |  |
| local compute (separate) |  | **unknown** (known part $0.000000 + 1 unknown item) |  |  | **unknown** (known part $0.000000 + 1 unknown item) |  |
| API total if verify used the Batch API (−50.0%, ESTIMATE ONLY, not the measured tier) |  | $15.722954 |  |  | $21.164409 |  |
| **elapsed time** |  |  | 3,770,920.0 s (1047.48 h) |  |  | 4,949,350.5 s (1374.82 h) |
| API per 1,000 input rows |  | $0.024964 |  |  | $0.033201 |  |
| **budget check** |  | within budget ($16.491704 ≤ $25.000000) |  |  | within budget ($21.933159 ≤ $25.000000) |  |

### Warnings

- ⚠ measured pilot enrich retry rate 1.000 is above the base-case assumption 0.050.

## 3. Rates used (`rates.csv`)

| provider | model | item | unit | price | currency | price per unit (× multiplier) | source | checked on | notes |
|---|---|---|---|---|---|---|---|---|---|
| typesafe | jev-* | input_uncached | token | 42 per 1,000,000,000 | USD | 0.000000042 | https://docs.typesafe.ai/primitives/choice | 2026-10-05 | Jev direct from TypeSafe: $42 per billion input tokens ($0.042 per 1M), as recorded in src/labelling/PREP.md (Jev section) and HANDOFF.md on 2026-10-05. RE-CHECK on the provider page before the pilot. |
| typesafe | jev-* | input_cached | token | **unknown** (blank) | USD | — | https://docs.typesafe.ai/primitives/choice | not checked | No cached-input rate is documented in the repo. Blank = unknown. Only matters if TypeSafe reports cached_input_tokens. |
| typesafe | jev-* | output | token | 0 per 1,000,000,000 | USD | 0 | https://docs.typesafe.ai/primitives/choice | 2026-10-05 | Output tokens free per src/labelling/PREP.md (Jev section, 'output free'). RE-CHECK before the pilot. |
| anthropic | claude-haiku-4-5* | input_uncached | token | 1.00 per 1,000,000 | USD | 0.000001 | https://platform.claude.com/docs/en/about-claude/pricing | 2026-10-06 | Claude Haiku 4.5 standard (non-batch) input, $1.00 per 1M tokens. From Anthropic's model table cached 2026-09-25, supplied by the orchestrator on 2026-10-06. Re-check before the pilot. |
| anthropic | claude-haiku-4-5* | input_cached | token | 0.10 per 1,000,000 | USD | 0.0000001 | https://platform.claude.com/docs/en/about-claude/pricing | 2026-10-06 | Prompt-cache read = 0.1x input ($0.10 per 1M). We do not use prompt caching; kept so any reported cached_input_tokens are priced, not dropped. Cache writes are not priced (not used). Re-check before the pilot. |
| anthropic | claude-haiku-4-5* | output | token | 5.00 per 1,000,000 | USD | 0.000005 | https://platform.claude.com/docs/en/about-claude/pricing | 2026-10-06 | Claude Haiku 4.5 standard output, $5.00 per 1M tokens (includes any thinking tokens). Anthropic returns no per-response cost, so this calculated cost is the bill. Batch API 50% discount is NOT applied here; it appears only as an estimated scenario. Re-check before the pilot. |
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

