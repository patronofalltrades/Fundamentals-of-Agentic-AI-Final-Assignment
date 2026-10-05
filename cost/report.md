# 100-review cost and runtime report

**Data source: MEASURED pilot** (collected from real run directories by `cost_calc.py collect`).

Generated offline by `python3 cost/cost_calc.py` from saved files only (no API key, no model calls). Spec: [docs/specs/COST_CALCULATOR.md](../docs/specs/COST_CALCULATOR.md). Rates multiplier in force: **1**.

## Inputs

| file | path | sha256 |
|---|---|---|
| assumptions.json | `cost/assumptions.json` | 5ed63dd510bb7a37… |
| local_compute.csv | `cost/local_compute.csv` | eb46ef302735cf79… |
| pilot_calls.jsonl | `cost/pilot_calls.jsonl` | 978404d8eba5bc87… |
| pilot_records.jsonl | `cost/pilot_records.jsonl` | d4c23a53a609d0db… |
| pilot_timing.json | `cost/pilot_timing.json` | bcf0a6e51fecb042… |
| rates.csv | `cost/rates.csv` | 6715f9ce75d498fb… |
| usage.csv | `cost/usage.csv` | 83d286e4a27308f7… |

## 1. Measured 100-review pilot (cold vs warm)

### 1.1 Input and records

|  | cold | warm |
|---|---|---|
| input file / checksum (sha256) | cost_100.csv / `c884ac3b9be5066995d5063f96ad9af6e5e082975788c1684c4f6b6ea661dd0e` | same input |
| checksum matches manifest | ✓ docs/specs/manifest.json | — |
| IDs (expected 100) | 100 ✓ match CSV | same IDs |
| run id | pilot-cold | pilot-warm |
| completed records | 100 | 100 |
| failed / quarantined records | 0 | 0 |
| pending (no record) | 0 | 0 |
| nonempty texts / empty texts | 100 / 0 | same |
| unique nonempty texts | 100 | same |
| reviews sent to enrich (succeeded calls) | 100 | 0 |
| result-cache hits (completed, not sent in this run) | 0 | 100 |
| new enrichment calls | 3 | 0 ✓ zero |

`pilot_records.jsonl`: 100 lines; 0 quarantined for a reason other than empty text (fix before scaling).

### 1.2 Per-stage settings (declared in run_config.json; observed in calls)

| stage | run | provider | exact model ID | effort | prompt / schema version | label_config | reviews per request | workers |
|---|---|---|---|---|---|---|---|---|
| enrich | cold | typesafe | jev-1.13.0 | declared: none | **unknown** / **unknown** | typesafe/jev-latest:prompt-v1:extract-v2:schema-a5-v1 | 28–36 (mean 33.3) (declared max 50) | 1 |
| enrich | warm | declared: typesafe | declared: jev-latest | declared: none | **unknown** / **unknown** | declared: typesafe/jev-latest:prompt-v1:extract-v2:schema-a5-v1 | no calls (declared max 50) | 1 |
| verify | cold | anthropic | claude-haiku-4-5-20251001 | declared: none | **unknown** / **unknown** | — | 20–20 (mean 20.0) (declared max **unknown**) | 1 |
| verify | warm | declared: anthropic | declared: claude-haiku-4-5 | declared: none | **unknown** / **unknown** | — | no calls (declared max **unknown**) | 1 |
| group | cold | anthropic | claude-haiku-4-5-20251001 | declared: none | **unknown** / **unknown** | — | — (saved aggregate pack) | 1 |
| group | warm | declared: anthropic | declared: claude-haiku-4-5 | declared: none | **unknown** / **unknown** | — | — (saved aggregate pack) | 1 |
| memo | cold | anthropic | claude-haiku-4-5-20251001 | declared: none | **unknown** / **unknown** | — | — (saved aggregate pack) | 1 |
| memo | warm | declared: anthropic | declared: claude-haiku-4-5 | declared: none | **unknown** / **unknown** | — | — (saved aggregate pack) | 1 |

### 1.3 Requests and attempts

| stage | run | attempts | succeeded | failed | retries (attempt>1) | fallbacks | uncertain charge (timeouts) | reviews in succeeded calls |
|---|---|---|---|---|---|---|---|---|
| enrich | cold | 3 | 3 | 0 | 0 | 0 | 0 | 100 |
| enrich | warm | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| verify | cold | 1 | 1 | 0 | 0 | 0 | 0 | 20 |
| verify | warm | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| group | cold | 1 | 1 | 0 | 0 | 0 | 0 | 42 |
| group | warm | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| memo | cold | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| memo | warm | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

Verification calls are the `verify` rows. Failed attempts are listed with their error in `pilot_calls.jsonl`.

### 1.4 Usage and cost by stage (API)

| stage | run | input uncached (tokens) | input cached (tokens) | output (tokens) | reasoning (tokens) | calculated cost | provider-reported cost_usd | calculated − reported |
|---|---|---|---|---|---|---|---|---|
| enrich | cold | 90,629 | not reported | 33,561 | not reported | $0.003806 | **unknown** (not reported) | — |
| enrich | warm | — | not reported | — | — | $0.000000 | — | — |
| verify | cold | 1,884 | 0 | 1,083 | not reported | $0.007299 | none (Anthropic returns no per-call cost; calculated = bill) | — |
| verify | warm | — | not reported | — | — | $0.000000 | — | — |
| group | cold | 1,746 | 0 | 1,127 | not reported | $0.007381 | none (Anthropic returns no per-call cost; calculated = bill) | — |
| group | warm | — | not reported | — | — | $0.000000 | — | — |
| memo | cold | 4,535 | 0 | 944 | not reported | $0.009255 | none (Anthropic returns no per-call cost; calculated = bill) | — |
| memo | warm | — | not reported | — | — | $0.000000 | — | — |

### 1.5 Totals, time and throughput

|  | cold | warm (incremental) |
|---|---|---|
| API spend (all stages) | $0.027741 | $0.000000 |
| local compute (separate, from local_compute.csv) | **unknown** (known part $0.000000 + 1 unknown item) | **unknown** (known part $0.000000 + 1 unknown item) |
| end-to-end wall clock (invocations.jsonl) | 34.82 s | 0.81 s |
| enrich time (request durations summed / first start→last end) | 2.68 s summed / 2.69 s span | 0 calls |
| verify time (request durations summed / first start→last end) | 9.67 s summed / 9.67 s span | 0 calls |
| group time (request durations summed / first start→last end) | 9.06 s summed / 9.06 s span | 0 calls |
| memo time (request durations summed / first start→last end) | 12.50 s summed / 12.50 s span | 0 calls |
| stage `enrich` (invocation timer) | 2.69 s | 0.00 s |
| stage `group` (invocation timer) | 9.07 s | 0.01 s |
| stage `ingest` (invocation timer) | 0.00 s | 0.00 s |
| stage `memo` (invocation timer) | 12.51 s | 0.00 s |
| stage `rank` (invocation timer) | 0.00 s | 0.00 s |
| stage `verify` (invocation timer) | 9.67 s | 0.00 s |
| throughput (input rows / wall second) | 2.872 | 122.699 |
| API cost per 1,000 input rows | $0.277414 | $0.000000 |
| API cost per completed record | $0.000277 | $0.000000 |
| pilot budget | $1.000000 | cold + warm: $0.027741 |

Summed request durations can exceed wall clock when calls overlap; wall clock comes from `invocations.jsonl`.

## 2. Full-run estimate (editable assumptions, not measured)

Per-unit basis: **measured cold pilot**. Each stage is extrapolated from its own work count; group and memo are one-time overhead counted once.

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
| measured pilot enrich retry rate (retries / succeeded calls) | 0.000 |
| fallback fraction base / conservative | 0.0 / 0.0 |
| fixed-overhead multiplier base / conservative | 1.0 / 2.0 |
| concurrency efficiency base / conservative | 1.0 / 0.6 |
| output-token cap per call | {"enrich": null, "group": 1500, "memo": 2500, "verify": 1700} |
| reasoning tokens included in output | True |

Output-token caps vs observed, and worst-case output cost of one call at the cap:

| stage | declared cap | max observed output tokens | worst-case output cost per call |  |
|---|---|---|---|---|
| enrich | not declared (unknown) | 12091 | **unknown** (known part $0.000000 + 1 unknown item) |  |
| verify | 1700 | 1083 | $0.008500 |  |
| group | 1500 | 1127 | $0.007500 |  |
| memo | 2500 | 944 | $0.012500 |  |

### 2.3 Per-unit basis

| stage | unit | basis | API cost per unit | input tok/unit | output tok/unit | time |
|---|---|---|---|---|---|---|
| enrich | per review sent | pilot | $0.000038064 | 906.3 | 335.6 | 37.286 reviews/s per worker |
| verify | per review sent | pilot | $0.000364950 | 94.2 | 54.1 | 2.069 reviews/s per worker |
| group | once per run (fixed) | pilot | $0.007381 | — | — | 9.06 s |
| memo | once per run (fixed) | pilot | $0.009255 | — | — | 12.50 s |
| fallback | per review routed | none | **unknown** (no fallback calls measured) | — | — | — |
| local overhead | per input row | pilot | $0 API | — | — | 9.050 ms/row (wall − summed call time, ÷ pilot rows; linear, upper bound) |

### 2.4 Base case (retry 0.050, fallback 0.0000, fixed ×1.0, 2.00 effective workers)

| stage | work (reuse) | API cost (reuse) | time (reuse) | work (no reuse) | API cost (no reuse) | time (no reuse) |
|---|---|---|---|---|---|---|
| enrich | 484,189 | $19.351770 | 6,817.6 s (1.89 h) | 660,609 | $26.402817 | 9,301.7 s (2.58 h) |
| fallback | 0 | $0.000000 | 0.00 s | 0 | $0.000000 | 0.00 s |
| verify | 2,000 | $0.766395 | 507.47 s | 2,000 | $0.766395 | 507.47 s |
| group | 1 | $0.007750 | 9.51 s | 1 | $0.007750 | 9.51 s |
| memo | 1 | $0.009718 | 13.13 s | 1 | $0.009718 | 13.13 s |
| local overhead (ingest/rank/export) | 660,622 | $0.000000 | 5,978.6 s (1.66 h) | 660,622 | $0.000000 | 5,978.6 s (1.66 h) |
| **API total** |  | $20.135633 |  |  | $27.186680 |  |
| local compute (separate) |  | **unknown** (known part $0.000000 + 1 unknown item) |  |  | **unknown** (known part $0.000000 + 1 unknown item) |  |
| API total if verify used the Batch API (−50.0%, ESTIMATE ONLY, not the measured tier) |  | $19.752435 |  |  | $26.803482 |  |
| **elapsed time** |  |  | 13,326.4 s (3.70 h) |  |  | 15,810.4 s (4.39 h) |
| API per 1,000 input rows |  | $0.030480 |  |  | $0.041153 |  |
| **budget check** |  | within budget ($20.135633 ≤ $25.000000) |  |  | ⚠ EXCEEDS BUDGET ($27.186680 > $25.000000) |  |

### 2.5 Conservative case (retry 0.250, fallback 0.0000, fixed ×2.0, 1.60 effective workers)

| stage | work (reuse) | API cost (reuse) | time (reuse) | work (no reuse) | API cost (no reuse) | time (no reuse) |
|---|---|---|---|---|---|---|
| enrich | 484,189 | $23.037822 | 10,145.3 s (2.82 h) | 660,609 | $31.431925 | 13,841.8 s (3.84 h) |
| fallback | 0 | $0.000000 | 0.00 s | 0 | $0.000000 | 0.00 s |
| verify | 2,000 | $0.912375 | 755.16 s | 2,000 | $0.912375 | 755.16 s |
| group | 1 | $0.018452 | 22.65 s | 1 | $0.018452 | 22.65 s |
| memo | 1 | $0.023138 | 31.26 s | 1 | $0.023138 | 31.26 s |
| local overhead (ingest/rank/export) | 660,622 | $0.000000 | 5,978.6 s (1.66 h) | 660,622 | $0.000000 | 5,978.6 s (1.66 h) |
| **API total** |  | $23.991787 |  |  | $32.385890 |  |
| local compute (separate) |  | **unknown** (known part $0.000000 + 1 unknown item) |  |  | **unknown** (known part $0.000000 + 1 unknown item) |  |
| API total if verify used the Batch API (−50.0%, ESTIMATE ONLY, not the measured tier) |  | $23.535599 |  |  | $31.929702 |  |
| **elapsed time** |  |  | 16,933.0 s (4.70 h) |  |  | 20,629.5 s (5.73 h) |
| API per 1,000 input rows |  | $0.036317 |  |  | $0.049023 |  |
| **budget check** |  | within budget ($23.991787 ≤ $25.000000) |  |  | ⚠ EXCEEDS BUDGET ($32.385890 > $25.000000) |  |

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

