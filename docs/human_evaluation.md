# Human golden evaluation

All 50 answers must be written by a human before final evaluation. No answers
were generated. The verified source contains 50 rows and 350 blank label cells.
Its original SHA-256 is
`1a125c3e509f58b0246ba16d0ea332675a53ffadb1928be4338a0bd7053a11c7`.

A byte-identical, blank working copy is saved in the task's sibling
`human-evaluation/golden_50_human_labels.csv`, outside this repository.
An Excel workbook, `human-evaluation/golden_50_human_labels.xlsx`, is beside it.
The workbook has dropdowns for topic, intent, severity and needs-review on all
50 rows. Sentiment has a decimal range check from -1 to 1. Entities and the
exact quote remain manual. All 350 answer cells start blank. Source columns
are shaded gray; answer columns are amber. Review rating is visually muted.
The local handoff provides its absolute path. Preserve the original source
CSV. Do not publish or send expected answers to any model.

Keep the six source columns and row IDs unchanged. Fill only `topic`, `intent`,
`sentiment`, `severity`, `entities`, `evidence_quote`, and `needs_review`.
Topics: `access`, `usability`, `playback`, `downloads`, `catalog`, `billing`,
`support`, `other`. Intents: `cancellation`, `complaint`, `request`, `praise`,
`unclear`. Use sentiment from -1 to 1; severity
integer 1–5; entities as a JSON array of strings (or `[]`); an evidence quote
copied exactly from the review; and `true` or `false` for `needs_review`.
Use the assignment contract's intent vocabulary and guidance.

Open and edit the `.xlsx` workbook, then save it. From the repository root, run:

```sh
python3 tools/export_human_labels.py --workbook ../human-evaluation/golden_50_human_labels.xlsx --source ../human-evaluation/golden_50_human_labels.csv --out ../human-evaluation/golden_50_human_labels_completed.csv
```

The exporter uses Python's standard library. It requires 50 complete rows,
checks exact source field strings and the pinned blank-template checksum, and
validates answer enums, numeric ranges, entities JSON, the exact quote, and
the boolean. It refuses existing output paths. Validation is mechanical; it
does not judge human label correctness. The initial blank workbook correctly
fails export. No completed answer CSV exists yet.

The evaluator is not implemented yet. When added, it must fail until all 50
human answers are validated. Prediction model inputs contain original text
only; expected columns must stay isolated. Report the known six-row/five-text
overlap with development records. Do not use golden answers for tuning.
