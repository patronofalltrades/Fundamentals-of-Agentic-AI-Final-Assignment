# Cost and runtime calculator (100-review pilot)

This folder is the `cost/` deliverable from `COST_CALCULATOR.md`. The pilot ran on 12 October 2026 on the
unchanged course file `cost_100.csv` (SHA-256 `c884ac3b…dd0e`). It used one worker, and had a cold run and a
warm run. The full report is [reports/cost100-pilot.md](../reports/cost100-pilot.md).

The calculator has two parts:

- **Measured:** it bills every saved pilot call again, from its recorded usage and the editable dated rates.
- **Estimated:** it scales each stage to the full corpus by that stage's own work count.

Neither part needs an API key or the network. Importing or running the calculator never makes a model call.

## 1. Offline replay (default)

```sh
python3 -m tools.cost100_offline_calculator                                        # measured pilot only
python3 -m tools.cost100_offline_calculator --scenario cost/scenario_full.json     # plus full-run estimates
python3 -m tools.cost100_offline_calculator --scenario cost/scenario_full.json --projected-records 110000
python3 -m tools.cost100_offline_calculator --rates my-rates.json --scenario cost/scenario_full.json
```

**To change an assumption:**

- **Prices:** copy `pilot/rates.json`, edit the four `*_usd_per_million` values, and pass the copy with `--rates`.
- **Other assumptions:** copy `scenario_full.json`, then edit the budget, retry and fallback fractions, verifier
  sample, complaint share, output-token growth or cap, memo calls, or maximum concurrency.

**What the tests and the [saved check](../reports/cost100-offline-checks.json) confirm:**

- Doubling every rate doubles the measured and the estimated API cost, and leaves all times unchanged.
- Changing the projected record count never changes the measured 100-review results.
- The memo is one-time work, so its cost does not grow with the record count.
- A scenario above the budget is flagged with a warning.

The tests are in `tests/test_cost100_calculator.py`.

## 2. Measured result (cold run, one worker)

| Stage | Provider and model | Settings | Calls (outcomes) | Work | API charge (US$) |
| --- | --- | --- | --- | --- | ---: |
| Labels: topic, intent, severity | TypeSafe `jev-1.13.0` | effort `systemone`, prompt `jev-rubric-v2`, schema `jev-labels-v1`, 1 review per call | 100 (100 succeeded) | 100 reviews | 0.004262454 |
| Evidence quotes | DeepInfra `openai/gpt-oss-120b` | 25 reviews per call | 4 (2 succeeded, 2 failed) | 100 reviews; 98 accepted, 2 quarantined | 0.001762679 |
| Blind verifier | DeepInfra `openai/gpt-oss-120b` | 10-review sample | 1 (succeeded) | 10 reviews | 0.000190312 |
| Issue grouping | DeepInfra `openai/gpt-oss-120b` | up to 10 records per call | 6 (succeeded) | 51 complaint and cancellation records | 0.001128357 |
| Ranking | code | — | 0 | — | 0 |
| Memo | DeepInfra `openai/gpt-oss-120b` | saved aggregates only | 1 (succeeded) | one-time | 0.000066485 |
| **Total** | | | **112** | **98 of 100 completed** | **0.007410287** |

- **Usage:** recorded for all 112 calls, 132,136 input and 31,497 output tokens. The rates are dated
  2026-10-12, with source links in `pilot/rates.json`. Jev output is free.
- **Unit cost:** US$0.074103 per 1,000 input rows and US$0.000076 per completed record.
- **Cold run:** 588.4 s of active stage time. The wall time from the first to the last stage was 1,581.2 s.
  That includes 992.8 s of interruptions and approval pauses, so it is not uninterrupted throughput.
- **Warm run:** 0.008 s from saved results, with **zero** new model calls.
- **Interruption and resume:** `pilot/checkpoint_before.json` has 0 completed IDs, and
  `pilot/checkpoint_after.json` has 98. The 12 resumed calls sent no completed ID again.
- **Local compute cost:** unknown, not zero.

## 3. Full-run estimate (all 660,622 source rows)

These are estimates, not measurements. All 660,622 rows are accounted for: 660,609 nonempty texts get
outputs, and the 13 empty texts are quarantined with no call. Exact-text reuse sends 484,189 distinct texts;
without reuse, all 660,609 are sent.

| Case | Exact-text reuse | API cost (US$) | Modeled elapsed time | Within US$49.99? |
| --- | --- | ---: | ---: | --- |
| Base | yes | 35.11 | 186 h at 4 workers | yes |
| Base | no | 46.29 | 247 h at 4 workers | yes |
| Conservative | yes | 48.33 | 496 h at 2 workers | yes, close to the limit |
| Conservative | no | 62.89 | 651 h at 2 workers | **no: warning** |

**How each stage scales.** Each stage uses its own measured tokens and seconds per unit of work:

| Stage | Unit of work |
| --- | --- |
| Labels and evidence | each text sent |
| Verifier | each sampled text |
| Grouping | each complaint or cancellation record |
| Memo | one-time work, not scaled |

**The two cases:**

| Assumption | Base | Conservative |
| --- | --- | --- |
| Retries | 2%: the pilot's 2 quote failures in 100 | 10% |
| Fallback | 0% | 5% of evidence work at 10 times the evidence cost. No stronger fallback model is configured. |
| Complaint share | 30.3%: the main run, 30,400 of 100,229 | 51%: the pilot, 51 of 100 |
| Output tokens | as measured | 25% more |
| Memo calls | 1 | 3 |

**Cross-check against the real 100k run.** Projected to 110,000 rows, the base case with reuse estimates
US$5.85. Of that, labels are US$3.50 and evidence US$1.45, together US$4.95. All 79,797 calls of the 110,000-review
run measured US$3.26 for Jev labels and US$1.46 for DeepInfra evidence, together US$4.73
([call aggregate](../reports/run-110k-calls-aggregate.json)). Labels are estimated about 7% high; evidence is within
1%. The other US$0.90 of the estimate is the verifier, grouping and memo. The main run did these as agent handoffs
with no metered usage, so they have no measured counterpart.

Two measured totals exist; each names its scope. The full run (all calls in the grading release) is US$4.73. The
scale queue alone, which accepted 90,663 of the 100,229 reviews, is US$4.21: Jev US$2.92 and DeepInfra US$1.29
([completion report](../reports/accepted-100k-completion.md)). The other US$0.51 is the two earlier checkpoint
ledgers (`checkpoint_requests` and `next5000_requests`), which accepted the remaining 9,566 reviews.

**Time is modeled.** Elapsed time assumes linear speed-up up to the worker limit. It is pessimistic, because
the pilot's Jev calls took 2.5 s for 1 review each, while the main run's median was 0.32 s per one-review request.

## 4. Scaling decision

- **Budget:** strictly below US$50 for the whole project. The ceiling is US$49.99. The main run also had
  separate caps of US$5 for Jev and US$5 for OpenRouter.
- **Scope:** the instructor set a minimum of 100,000 reviews. The project ran 110,000 selected reviews for
  US$4.73 in metered charges. The full corpus was not run: the base estimate fits the budget, but the conservative
  no-reuse case does not, and the deadline did not allow 186 hours or more of modeled run time.
- **Batching:** one review per Jev request in the main run (76,523 requests), not the 10 per request the instructor
  asked for. Evidence requests sent up to 25 distinct texts each (3,274 requests). The contract allows up to 50.
- **Concurrency:** start at one worker, as in the pilot. Raise it only while rate limits and the shared spend
  ledger allow. The estimate uses 4 workers (base) and 2 (conservative).
- **Fallback:** none. A failed or uncertain call is never sent to a stronger model automatically. Uncertain
  outcomes are held, not retried.
- **Spend controls:** a shared ledger reserves the worst-case cost before each call, and stops admitting work
  when spent plus reserved plus the next reservation would exceed the cap.

## 5. Explicit pilot execution (paid; needs approval)

`tools/cost100_harness.py` runs the pilot. Without `--execute` it only prints an offline plan.

```sh
python3 -m tools.cost100_harness --source cost_100.csv --out local/cost100_pilot                       # offline plan
python3 -m tools.cost100_harness --source cost_100.csv --out local/cost100_pilot --execute \
  --approved-cap-usd 0.36 --pause-after evidence                                                         # cold run, stops after evidence
python3 -m tools.cost100_harness --source cost_100.csv --out local/cost100_pilot --execute \
  --approved-cap-usd 0.36 --resume                                                                       # resume the remaining stages
python3 -m tools.cost100_harness --source cost_100.csv --out local/cost100_pilot --replay               # warm run, zero calls
```

A paid run needs `TYPESAFE_API_KEY` and `OPENROUTER_API_KEY` in the environment, or the macOS keychain. It
refuses to start while any reservation is still open.

## Files

| File | Contents |
| --- | --- |
| `pilot/pilot_records.jsonl` | One result per pilot ID: original review ID, source row hash, status, common labels and evidence |
| `pilot/pilot_calls.jsonl` | One line per attempt: role, phase, provider, model, label configuration, review IDs, tokens, charge, reservation, timing, outcome |
| `pilot/rates.json` | Editable dated rates in US$ per million tokens, with source links |
| `pilot/report.json` | Saved totals and stage timings |
| `pilot/checkpoint_before.json`, `pilot/checkpoint_after.json` | `completed_ids` before the interruption and after the resume |
| `scenario_full.json` | Editable full-run assumptions for the estimate |
| `measurements.json`, `rates.json`, `scenario.json` | The earlier offline scaffold for `python3 -m spotify_pipeline cost`. They hold no pilot data. |

The pilot IDs are original review IDs from the CC0 course dataset, published so the instructor can check them
against `cost_100.csv`. No full review text is included; evidence quotes are exact substrings of the source text.
