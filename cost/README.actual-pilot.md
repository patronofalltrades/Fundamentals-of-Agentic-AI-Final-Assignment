# Actual 100-review pilot calculator

The saved private pilot is in
`local/grading_v4_submission_candidate/cost100_pilot_separate/`. Its `pilot_calls.jsonl`,
`rates.json`, and `report.json` contain actual metered usage and measurements.
The tracked `cost/measurements.json` and `cost/rates.json` are older null
scaffolds; they do not represent this pilot or its two provider-specific rates.

Offline replay, with no credentials or network calls:

```sh
python3 -m tools.cost100_offline_calculator --pilot local/grading_v4_submission_candidate/cost100_pilot_separate --projected-records 100
python3 -m tools.cost100_offline_calculator --pilot local/grading_v4_submission_candidate/cost100_pilot_separate --projected-records 100000
```

Pass an edited copy of the private pilot `rates.json` with `--rates` to change
the four API token rates. [Saved check results](../reports/cost100-offline-checks.json)
show that doubling all four rates doubles the recalculated API subtotal while
leaving measured time intact. Changing the projected record count leaves the
100-review measurements intact. The calculator deliberately leaves the
full-run projection unavailable because no stage-specific scaling assumptions
have been supplied. Local compute cost is unknown.

The warm replay checks the saved artifacts and makes no model call. The original
0.008-second warm event checked coverage, verifier IDs, ranking, and memo
claims. A later read-only validation added source/configuration and cache input
hash checks, exact evidence validation, and grouping coverage. It took 0.019757
seconds without changing the saved call count. Neither warm pass regenerates
model outputs. The cold run accepted 98 of 100 evidence rows; two metered quote
failures remain quarantined.
