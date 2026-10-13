# Spotify 500-review checkpoint: current readiness (October 7, 2026)

**Assessment:** The 500-review development checkpoint is a sound *structural*
foundation. It is not yet a defensible product-priority result or a ready
100,000-review pipeline. With the October 13 Pacific deadline, the final
submission is at risk until a measured extractor, complete runtime stages,
and deployed dashboard/backend/database are working. This report uses saved
development results only. Human golden answers were not read.

## What is working

The supplied 500-row file passed its manifest SHA-256 and byte checks. The
frozen Jev v2 configuration has **500/500 original IDs** in the canonical
checkpoint database, with zero pending. There are **479 distinct exact
texts**: 479 direct Jev labels and 21 exact-text label reuses. The 400-row
extension made 379 new settled Jev calls with no Jev retry or failure.
Evidence has 500 exact-source records; the extension made 379 successful
new Codex evidence calls and reused 21 same-text results. Quotes and entity
spans match their own source text; saved cache provenance points to direct
originals. An offline replay validated 500 records in **0.017 seconds** with
zero new model calls. These checks establish identity, completeness, saved
state, and source-span integrity. They do **not** establish that labels or
quotes express the right customer problem.

The new Jev extension used 384,476 input and 74,460 output tokens, costing
**$0.016147992** at its recorded input-token rate. The cumulative v1, v2,
and checkpoint Jev charge is **$0.024101700**. Its new label-stage wall time
was **127.0 seconds**. The 379 successful new Codex evidence calls reported
6,955,138 input tokens, 5,438,848 of those cached, and 11,953 output tokens;
their summed request time was **2,567.5 seconds**. Codex incremental dollars
and full evidence-stage wall time are **unknown**, not zero. One interrupted
Codex attempt has unknown delivery/usage and a linked successful retry.

## What the saved labels say, and what they do not

| Saved model output | Count | Reading |
| --- | ---: | --- |
| `other` | 289 (57.8%) | Includes 184 praise and 75 complaint/cancellation rows; not all are extraction failures. |
| `usability` / `playback` / `billing` / `catalog` | 64 / 52 / 40 / 34 | Candidate issue signals, not verified prevalence. |
| `downloads` / `access` / `support` | 12 / 9 / 0 | Zero support labels may reflect this sample or model routing. |
| complaint / cancellation / praise / request / unclear | 217 / 30 / 213 / 12 / 28 | 247 candidate complaint/cancellation rows need issue membership and ranking. |
| `needs_review` | 387 (77.4%) | All 289 `other` rows plus 98 specific-topic rows are flagged. |
| severity 1 / 2 / 3 / 4 / 5 | 258 / 108 / 72 / 59 / 3 | Predicted severity, not a calibrated harm distribution. |

A selected positive sign: a complaint about being allowed only six skips was
classified as `usability`, severity 3, which fits the rubric's controls rule.
A selected concern: a review saying it was “limited on the skips” was labeled
`playback`, complaint, severity 3, with `needs_review=false`; that control
complaint appears to belong under `usability`. Earlier manual development
reading also found a likely sparse-genre `catalog` miss. One non-English
severity-5 prediction still needs independent judgment on whether it states
the serious harm required for level 5. These are unblinded selected cases,
not an accuracy sample. No golden accuracy, macro F1, or human agreement has
been measured. Six golden rows share five exact texts with development data;
that overlap must be disclosed in a future evaluation.

## Scale and grade readiness

The instructor's user-reported clarification sets **100,000 source reviews**
as the minimum, with an approximate **$10** expectation, not a measurement
or spending approval. The earlier full-corpus plan remains a stretch target.
The supplied grading contract still specifies all 660,622 source IDs, so the
scoped export's acceptance must be verified and disclosed. Each selected
original ID must remain in output even if exact-text caching saves calls.

The profiled first 100,000 source rows contain 99,999 nonempty reviews, one
empty review, and **75,894 distinct nonempty texts**. Compatible reuse from
the checkpoint could leave **75,760 new distinct texts**. Linear Jev-only
extrapolation is about **$3.23 and 7.1 serial hours** for those calls. It
excludes evidence, verifier, grouping, memo, retries, and local overhead.
Repeating the saved per-review Codex evidence approach would imply roughly
**143 serial hours** and 1.39 billion reported input tokens; its dollar cost
is unknown. Neither route is a measured end-to-end 100,000-row plan.

The hosted extractor comparison is also **held**: its separate $1-cap ledger
has one successful DeepInfra request ($0.000014102 usage-derived charge) and
one uncertain POST with a $0.024903544 reservation. No Groq result exists.
Reconcile that attempt's billing and delivery before more inference. The
current [extractor report](openrouter-extractor-benchmark.md) records the
safe handoff. The $1 pilot cap remains unchanged.

Still missing: independent blind verification; accepted issue membership;
code-owned `severity_sum` ranking; checked memo claims; the grading export
and supplied self-check; a real 100-review cold/warm run through all stages;
human-label evaluation; and a deployed dashboard, backend, database, and live
URL in the README. The offline 0.017-second replay covers only saved
classification/evidence handoff, not that end-to-end requirement.

## Critical path to October 13 Pacific

1. **Resolve the held extractor POST and choose a route.** Reconcile OpenRouter
   activity without sharing keys or review text. Finish the same-review bounded
   comparison only if privacy, route, quality, throughput, and cumulative cap
   checks pass. Keep Jev for fixed labels unless measured evidence warrants a
   change.
2. **Complete the contract pipeline.** Build blind verification, durable
   queue/checkpoints, configuration-safe cache, issue membership, deterministic
   ranking, memo claim checks, grading export, and offline cost replay. For
   scale, test **10 reviews in one model request**, with per-ID results,
   bounded parallel workers, atomic shared spend reservations, and safe
   retries/resume. Ten parallel one-review calls are a different design.
3. **Build deployment in parallel.** Use the saved checkpoint to exercise a
   backend/database and dashboard. Verify the deployed result and put its live
   URL in the README; do not wait for the 100,000-row inference to start UI
   work.
4. **Gate the large run.** Measure a true cold/warm 100-review end-to-end run,
   then 500 and 10,000 with actual attempts, usage, cost, latency, failures,
   and quality review. Reconcile the 100,000-row scope with the supplied
   full-corpus checker. Obtain separate spending approval before scale.

Sources: [500 checkpoint report](checkpoint-500-readiness.md), [aggregate
checkpoint data](jev-checkpoint-500.json), read-only saved Jev v2 labels and
canonical classifications, and [hosted extractor status](openrouter-extractor-benchmark.md).
