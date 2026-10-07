# Spotify checkpoint 500: measured result and assignment readiness

**Decision:** The frozen-rubric development checkpoint is structurally complete.
The assignment pipeline is **not ready for a 100,000-review inference run**.
Verification, issue grouping, ranking, memo writing, the grading export, real
human agreement, and a measured full cold/warm cost calculator remain open.
The next 100,000 reviews were profiled read-only for planning; no inference
was run on them.

## Saved 500-review result

The supplied `checkpoint_500.csv` passed its manifest SHA-256 and byte checks.
Its source hash is `a94e31663ee7b7eaa77e23b7a8425b530cc0c866ed5e714953172a0afef6a12f`.
All 500 original IDs have frozen `jev-rubric-v2` / `jev-labels-v1` labels and
exact source evidence in a separate ignored checkpoint ledger. A separate
canonical database accepted 500 complete records, with zero pending. The
first 100 rows came unchanged from the saved v2 pilot. No golden answer file
was opened or supplied to a model.

| Measured item | Result |
| --- | ---: |
| Direct Jev classifications / exact-text label reuses | 479 / 21 |
| New Jev calls for 400 added IDs | 379 settled; zero retries or failures |
| New Jev input / output tokens | 384,476 / 74,460 |
| New Jev charge at [published $0.042/M input](https://docs.typesafe.ai/models) | $0.016147992 |
| Cumulative v1 + v2 + checkpoint Jev charge | $0.024101700, under the $0.60 cap |
| New label-stage wall / summed request seconds | 127.023306667 / 125.411129958 |
| Exact evidence records / new direct Codex calls / new cache reuses | 500 / 379 / 21 |
| New Codex reported input / cached input / output tokens | 6,955,138 / 5,438,848 / 11,953 |
| New successful Codex summed request seconds | 2,567.544425266 |
| Offline saved-state warm replay | 500 records checked in 0.017149042 seconds; zero model calls |

All 500 quotes and entity spans match their own source text. Cached evidence
points directly to a same-text, same-label original and retains its source
model and prompt provenance. The 24 compatible v1 evidence copies retain
their earlier origin. The source, configuration, call-to-evidence mapping,
and final direct/cache membership passed deterministic validation.

The Codex CLI was logged in through ChatGPT. There was no paid API fallback.
The 379 new successful evidence attempts have reported token counts; the 76
older Codex attempts do not. One local sandbox startup failure was recorded
before the Codex app server initialized. During a connection loss, one later
attempt was interrupted with **unknown delivery and unknown usage**. Its
review was deferred until all other work completed, then retried once under
the user's authorization. Both attempts and their link remain in the ledger.
A separate synthetic route diagnostic consumed 18,086 input, 12,288 cached
input, and five output tokens; it is excluded from review evidence counts.
ChatGPT plan allowance and incremental dollar cost are unknown, not zero.
Nine successful evidence invocations have 2,053.254702416 seconds of summed
measured stage wall time. The interrupted invocation lacks a valid end time,
so the complete evidence-stage and end-to-end wall times are **unknown**.

## Quality reading and contract gates

Raw v2 topic counts are `other` 289, `usability` 64, `playback` 52, `billing`
40, `catalog` 34, `downloads` 12, `access` nine, and `support` zero.
`needs_review` is true on 387 records; 289 are flagged because they are
`other`. Severity counts are 258 at 1, 108 at 2, 72 at 3, 59 at 4, and three
at 5. These are model outputs, not product prevalence or quality scores.

Manual, unblinded development reading found the previously noted likely
catalog miss in a sparse-genre complaint. A skip-limit complaint fits the
contract's usability-controls rule. Among the three severity-5 predictions,
two describe apparent qualifying data or financial harm; one non-English
complaint warrants independent review for whether it reports the explicit
serious harm required by the contract. This is a selected judgment, **not**
accuracy, macro F1, or gold evaluation. No deterministic schema or source
mapping defect was found, and the rubric was not retuned.

| Requirement | Status | Evidence or remaining work |
| --- | --- | --- |
| Exact source identity and all 500 IDs | **Passed** | Manifest, source fields/hash, and 500 canonical records validated. |
| Label schema and exact evidence | **Passed mechanically** | 500/500 records; direct/cache provenance and source spans validated. Semantic correctness is unscored. |
| Measured Jev usage and cumulative cap | **Passed for checkpoint** | 379 new settled calls, measured token charge, pre-call reservation, no top-up. |
| Resumable evidence accounting | **Partial** | Saved calls resumed; one interrupted call's delivery/usage remains unknown and is explicitly linked to its retry. |
| Real cold/warm cost calculator | **Partial** | New Jev wall and request usage measured; offline saved-state warm replay made zero calls. Original 100-row wall and whole-pipeline cold/warm stages remain missing. |
| Independent blind verifier | **Not run** | No saved independent relabeling or disagreement sample. |
| Issue membership and `severity_sum` ranking | **Not run** | No accepted issue mapping or baseline ranking. |
| Memo and checked numerical claims | **Not run** | No product-priority recommendation can be supported yet. |
| Human golden evaluation | **Not run** | Human answers remain isolated. Six golden rows/five exact texts overlap development data; disclose this when evaluation is run. |
| Grading folder and supplied self-check | **Not run** | Full-corpus records, memberships, rankings, calls, checkpoints, and claims are not exported. |
| True end-to-end warm replay | **Not run** | Current warm replay covers saved classification/evidence handoff only. |

The supplied grading contract targets 660,622 full-corpus IDs,
660,609 nonempty classifications, and 13 empty-text quarantines. The 500-row
checkpoint does not substitute for those outputs. The supplied
`COST_CALCULATOR.md` requires an actual 100-review empty-cache pipeline run
through verification, grouping, ranking, and memo, followed by a warm repeat.
This remains materially incomplete despite the successful label/evidence
checkpoint.

## Read-only first-100,000 planning slice

The full source's manifest hash was verified. Its **first** 100,000 rows have
99,999 nonempty texts, one empty text, and 75,894 distinct nonempty exact
texts. Only 74 of the checkpoint's original IDs occur in this slice; it is
not a 500-row prefix. Among its distinct texts, 134 also occur in the saved
checkpoint, leaving 75,760 new distinct texts if compatible exact-text reuse
is implemented with direct original call provenance. This is one proposed
slice; no 100,000-row inference or output was created.

At the checkpoint's observed per-call mean, 75,760 new direct Jev calls would
cost approximately **$3.23** for labels and take **7.1 serial hours** of Jev
label-stage time. Without exact-text reuse, 99,999 calls would be about
**$4.26**. These are linear estimates, not reservations or approvals. They
exclude retries, rate changes, verification, evidence, grouping, memo, and
local overhead. Actual input lengths and model behavior may differ.

One Codex extraction per new distinct text would imply roughly **143 serial
hours** at the measured successful-call mean and about **1.39 billion
reported input tokens**, of which roughly 1.09 billion would be cached if the
same cache fraction persisted. The ChatGPT included-plan allowance and
incremental cost are unknown. The interrupted attempt's usage is also
unknown. This route is therefore **not demonstrated to fit the deadline or
budget** at 100,000 reviews. Parallelism, batching, a different evidence
model, or local inference may change the forecast, but each requires a small
measured quality/throughput/cost pilot against the same fixed contract before
a model decision. No new model route or 100,000-row run is approved here.

**Recommended next gate:** choose and benchmark a bounded evidence and
verification route; finish the code-owned issue mapping, ranking, memo claim
checks, grading export, and offline calculator; then measure a true
end-to-end cold/warm run. Keep the 100,000-row inference frozen until those
results and a separate budget authorization support it.

Supporting aggregate measurements are in [the checkpoint JSON](jev-checkpoint-500.json).
The local worktree remains unpublished. The offline suite passed **177 tests**;
the canonical import and saved-state replay were validated separately on the
real 500-row checkpoint.
