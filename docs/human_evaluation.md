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

## Severity and sentiment guide

Score these two fields independently from the review text. **Severity** is the
harm or loss of function the reviewer reports. **Sentiment** is the tone of
their words. Do not infer either score from the star rating. Anger and
cancellation intent alone do not raise severity. A severe problem can be
described calmly; a mild problem can be described angrily.

| Severity | Reported impact |
| --- | --- |
| 1 | No reported problem: praise, unclear or neutral content, or a pure feature request. |
| 2 | Minor annoyance, dislike, or general criticism without supported functional loss. |
| 3 | A function is degraded or restricted, but some use or a workaround remains. |
| 4 | A core task is clearly blocked. |
| 5 | Explicit serious financial, privacy, or data harm. |

When a review reports several problems, use the highest supported severity.
If problems tie, choose the first specific problem mentioned. Do not invent
impact that the review does not state.

Sentiment can be any decimal from **−1 to +1**. These optional anchors help
calibrate tone; they are not mandatory assignment bins:

| Anchor | Tone |
| ---: | --- |
| −1 | Very negative |
| −0.5 | Negative |
| 0 | Neutral or balanced |
| +0.5 | Positive |
| +1 | Very positive |

Intermediate decimals are allowed. Do not derive sentiment from severity.
For example, the invented review “Please fix sign-in. I cannot open my account
at all.” reports a blocked core task (severity 4) in a mildly negative tone.
The invented review “This app is awful!” has strongly negative tone but
reports only general criticism (severity 2). These examples are not from the
golden dataset and are not filled answers.

If the text leaves important context uncertain, set `needs_review` to `true`
and still provide your best human labels. Keep any uncertainty notes separate
from the source columns and exported answer CSV. Never ask a model to fill or
check expected golden answers.

Open and edit the `.xlsx` workbook, then save it. From the repository root, run:

```sh
python3 tools/export_human_labels.py --workbook ../human-evaluation/golden_50_human_labels.xlsx --source ../human-evaluation/golden_50_human_labels.csv --out ../human-evaluation/golden_50_human_labels_completed.csv
```

The exporter uses Python's standard library. It requires 50 complete rows,
checks exact source field strings and the pinned blank-template checksum, and
validates answer enums, numeric ranges, entities JSON, the exact quote, and
the boolean. It refuses existing output paths. Validation is mechanical; it
does not judge human label correctness. The initial blank workbook correctly
failed export when tested. A completed answer CSV requires explicit validated
export after the human has filled every answer.

The evaluator is not implemented yet. When added, it must fail until all 50
human answers are validated. Prediction model inputs contain original text
only; expected columns must stay isolated. Report the known six-row/five-text
overlap with development records. Do not use golden answers for tuning.
