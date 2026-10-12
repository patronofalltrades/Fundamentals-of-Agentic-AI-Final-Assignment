# Cost and runtime calculator (100-review pilot)

This folder is the `cost/` deliverable from `COST_CALCULATOR.md`. The pilot ran on 12 October 2026 on the
unchanged course file `cost_100.csv` (SHA-256 `c884ac3b…dd0e`), with one worker, a cold run and a warm run.
Full report: [reports/cost100-pilot.md](../reports/cost100-pilot.md).

## Recompute it (no API key, no network)

```sh
python3 -m tools.cost100_offline_calculator                                    # saved rates
python3 -m tools.cost100_offline_calculator --rates my-rates.json              # edited rates
python3 -m tools.cost100_offline_calculator --projected-records 100000          # scenario field only
```

To change prices, copy `pilot/rates.json`, edit the four `*_usd_per_million` values, and pass it with `--rates`.
Doubling every rate doubles the API total and leaves the measured times unchanged
([saved check](../reports/cost100-offline-checks.json); `tests/test_cost100_calculator.py`).

## Measured result

| Stage | Provider and model | Calls | Outcome | API charge (US$) |
| --- | --- | ---: | --- | ---: |
| Labels (topic, intent, severity) | TypeSafe `jev-1.13.0` | 100 | 100 accepted | 0.004262454 |
| Evidence quotes | DeepInfra `openai/gpt-oss-120b` | 4 (25 reviews each) | 98 accepted, 2 quarantined | 0.001762679 |
| Blind verifier | DeepInfra `openai/gpt-oss-120b` | 1 | saved | 0.000190312 |
| Issue grouping | DeepInfra `openai/gpt-oss-120b` | 6 | saved | 0.001128357 |
| Ranking | code | 0 | saved | 0 |
| Memo | DeepInfra `openai/gpt-oss-120b` | 1 | saved | 0.000066485 |
| **Total** | | **112** | **98 of 100 completed** | **0.007410287** |

- Usage is recorded for all 112 calls: 132,136 input and 31,497 output tokens. Rates are dated 2026-10-12, with
  source links in `pilot/rates.json`.
- **Cold run:** 588.4 s of active stage time. Wall time from first to last stage was 1,581.2 s, including
  992.8 s of interruptions and approval pauses, so it is not uninterrupted throughput.
- **Warm run:** 0.008 s from saved results, with **zero** new model calls.
- **Interruption and resume:** `pilot/checkpoint_before.json` has 0 completed IDs and 100 settled label calls;
  `pilot/checkpoint_after.json` has 98 completed IDs after the resumed stages (12 resumed calls). No completed ID
  was sent again.
- Local compute cost is unknown, not zero. A full-run projection is not given: it needs stage-specific scaling
  assumptions that have not been measured.

## Files

| File | Contents |
| --- | --- |
| `pilot/pilot_calls.jsonl` | One line per call: role, phase, provider, model, tokens, charge, timing, outcome. Review IDs are replaced by `review_count`; label request IDs are renumbered. |
| `pilot/rates.json` | Editable dated rates in US$ per million tokens |
| `pilot/report.json` | Saved totals and stage timings |
| `pilot/checkpoint_before.json`, `pilot/checkpoint_after.json` | Checkpoint counts. `private_file_sha256` is the hash of the unredacted checkpoint, which keeps the original IDs and stays private. |
| `measurements.json`, `rates.json`, `scenario.json` | The earlier offline scaffold for `python3 -m spotify_pipeline cost`. They hold no pilot data. |

The unredacted pilot files (with original review IDs) are kept outside Git. The grading folder's
`checkpoint_before.json` and `checkpoint_after.json` need the original `completed_ids` from those files.
