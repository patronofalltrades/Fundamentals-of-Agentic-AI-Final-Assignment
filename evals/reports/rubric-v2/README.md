# Topic rubric v2 vs v1 on the golden 50 (2026-10-06)

Rubric v2 = the Codex line's `jev-rubric-v2` topic wording, ported to `src/labelling/prompts.py` on branch
`feat/labelling-topic-rubric-v2` (58091b5). Same Jev model (`jev-1.13.0`), same extract-v2, three cold runs each.
v2 was written from development text only; it was measured once on the golden 50 and **not tuned on it**.

| Jev, 3 runs each | Topic | Intent | Severity | Joint | Topic macro-F1 (r1) |
|---|---|---|---|---|---|
| v1 vs original labels | 0.46–0.48 | 0.84–0.86 | 0.56 | 0.30 | 0.26 |
| v2 vs original labels | 0.46–0.48 | 0.86–0.88 | 0.56 | 0.30 | 0.31 |
| v1 vs adjudicated labels | 0.82–0.84 | 0.94–0.96 | 0.72 | 0.66 | 0.67 |
| v2 vs adjudicated labels | 0.80–0.82 | 0.96–0.98 | 0.72 | 0.64 | 0.64 |

Topic changed on 2 of 50 reviews (v1 → v2): one moved to the adjudicated label ("Banning conservative music…"
other → catalog), one moved away ("Duo Premium .... No ads at all!" billing → usability). Both are borderline.
v2 topic was unstable across its three runs on 1/50 reviews (v1: 1/50).

Cost: 52,300 input tokens per 50-review run vs 44,871 for v1 (+16.6%) — about +$0.0003 per run, and
roughly +$3 on the full-corpus Jev projection.

**Decision recommended: keep v1.** On this sample v2 shows no measurable gain (differences are within run
noise), costs about 17% more Jev input, and adopting it would change `label_config` and require re-running the
pilot. Jev already receives the full contract rubric text in `state.rubric`, which likely explains why sharper
choice criteria add little. Revisit only with a larger, blind-labelled sample.
