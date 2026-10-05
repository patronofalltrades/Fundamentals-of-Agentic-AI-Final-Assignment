# Evals: golden 50 human labels

- `golden_50_human_labels.csv` — **adjudicated** labels (version `golden-50-human-v2-adjudicated`, 2026-10-06), used by
  `build_gold.py`. `golden_50_human_labels.original.csv` is the original human labelling, unchanged;
  `golden_adjudication_log.csv` lists every changed field with the rubric rule (32 changes in 22 rows).
- `golden_50_human_labels.original.csv` — Hanif's original labels for all 50 rows of `golden_50_to_label.csv` (copied from
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

## Adjudication (2026-10-06) — disclose as a model-informed revision

After the first Jev evaluation, 31 disagreements were reviewed against `GRADING_CONTRACT.md`
(`reports/golden-disagreements.md`). Hanif asked for the rubric-decided rows to be corrected: 21 rows had a
field changed to the rubric's value (only that field; severity kept where the rubric does not decide), plus
one evidence-quote fix. The 10 ambiguous rows and the 1 row where the original label matched the rubric were
left as labelled. The adjudicated workbook (`golden_50_human_labels.adjudicated_20261006.xlsx`, with an
`Adjudication log` sheet) sits next to the original in the human-evaluation folder.

Because the adjudicator had seen Jev's predictions, agreement against the adjudicated labels is **optimistic**
and not an independent accuracy estimate. Both numbers are reported:

| Jev (3 cold runs) | Topic | Intent | Severity exact | Joint | Severity MAE |
|---|---|---|---|---|---|
| vs original labels | 0.46–0.48 | 0.84–0.86 | 0.56 | 0.30 | 0.64 |
| vs adjudicated labels | 0.82–0.84 | 0.94–0.96 | 0.72 | 0.66 | 0.38 |

An unbiased estimate needs fresh cases labelled blind to model output (e.g. a new sample from
`analysis_10000.csv` excluding the dev checkpoints), or the instructor's private benchmark.
