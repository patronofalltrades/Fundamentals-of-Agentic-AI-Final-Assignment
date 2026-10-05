# Jev vs golden 50 human labels (2026-10-06)

**Setup.** `run_labelling.py golden_50_to_label.csv --config configs/pilot_cost_100.json`, three independent cold
runs (`golden-jev-r1..r3`), Jev `jev-1.13.0` via TypeSafe, `label_config`
`typesafe/jev-latest:prompt-v1:extract-v2:schema-a5-v1`. Only review texts were sent; golden labels were read
only by `evals/score_gold.py` afterwards. Each run: 2 enrich calls (49 originals + 1 exact-text cache copy),
44,871 input tokens, 0 failures, about 1.5 s. Cost per run about $0.0019 (3 runs about $0.0057).

**Agreement with gold** (checker `score_gold`; missing predictions count as wrong — there were none):

| Run | Topic | Intent | Severity exact | Joint | Severity MAE |
|---|---|---|---|---|---|
| r1 | 0.46 | 0.84 | 0.56 | 0.30 | 0.64 |
| r2 | 0.48 | 0.84 | 0.56 | 0.30 | 0.64 |
| r3 | 0.48 | 0.86 | 0.56 | 0.30 | 0.64 |

Macro-F1 (r1): topic 0.26, intent 0.79, severity 0.29. Jev predicts `other` 28 times (gold 19), `usability`
8 times (gold 16), `support` never (gold 4), and severity 5 never (gold 4).

**Stability across the three runs:** topic changed on 1/50, intent 1/50, severity 0/50, needs_review 3/50.

**Interpretation — read before tuning.** Most disagreements are cases where the golden label appears to
depart from `GRADING_CONTRACT.md` (general praise labelled `usability`/`access`, ads labelled `support`/`other`,
severity 5 without financial/privacy/data harm, an explicit "Deleting this App" labelled `complaint`).
Of the 31 rows in `golden-disagreements.md`, the orchestrator's reading of the rubric favours Jev in 20, gold
in 1, and 10 are ambiguous. Until the golden labels are adjudicated against the rubric, these agreement numbers
understate Jev on topic and severity and must not be used to tune prompts. Intent agreement (0.84–0.86) is the
most trustworthy number here.
