# Evals: golden 50 human labels

- `golden_50_human_labels.csv` — Hanif's labels for all 50 rows of `golden_50_to_label.csv` (copied from
  `human-evaluation/golden_50_human_labels_completed.csv`, 2026-10-06). All 50 IDs and source fields match the
  supplied file; every label passes the grading schema; every evidence quote is an exact source substring.
  (The `.xlsx` working copy had one quote with a trailing space, `'Great... '`, which is not a substring; the CSV
  has the valid `'Great'`.)
- `build_gold.py` → `gold_benchmark.json` (checker `--gold` format: one accepted value per field, status
  `approved`) and `golden_50.jsonl` (full labels).
- `score_gold.py --run runs/<dir>` scores any run with the checker's own `score_gold`.

**Isolation.** Golden labels are never model inputs, examples, cache entries or routing thresholds.
`tests/test_gold_isolation.py` fails if any pipeline module or CLI references these files. The golden
**texts** are still classified in the full run like every other row.

**Overlap disclosure.** Six golden rows (five distinct texts) also occur in `analysis_10000.csv` under other IDs.
In the full run the exact-text cache may reuse a development-sample result for those texts; that reuse is
legitimate under the contract but means those six predictions were not produced blind to development work.

Label distribution: topic other 19, usability 16, support 4, playback 4, catalog 3, access 2, billing 2;
intent complaint 19, praise 19, unclear 9, request 3; severity 1:26, 2:9, 3:6, 4:5, 5:4; needs_review 12.
