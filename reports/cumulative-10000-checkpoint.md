# Development review checkpoint: 10,000 source rows

The frozen development selection covers source positions 1–10,000. Each selected source ID and contract source hash remains in the private handoff, including rows without accepted evidence. This is a structural checkpoint, not a product recommendation or a golden-answer evaluation. No 100,000-row run was started.

| Scope | Accepted label and evidence | Quarantined evidence | Uncertain or blocked | Pending or in flight |
| --- | ---: | ---: | ---: | ---: |
| First 5,000 | 4,649 | 285 | 66 | 0 |
| Next 5,000 | 4,917 | 48 | 35 | 0 |
| **Cumulative** | **9,566** | **333** | **101** | **0** |

In the next 5,000, 4,985 Jev labels were saved. Fifteen rows were held because their exact text matched an older uncertain evidence request. Twenty rows belong to two new uncertain ten-review requests. Those requests ended in a timeout and a connection reset; no response, usage, or generation ID was saved. Their two full reservations of $0.005545984 each remain held. No uncertain text was retried. One charged, malformed ten-review response had nine uniquely matched IDs and one unknown ID. Offline exact-span validation recovered the nine matching rows without another call; the missing ID stays quarantined. The raw response and charge remain saved.

The next 5,000 had 48 structural evidence quarantines: 32 exact-quote failures, 15 entity-span failures, and the one missing-ID row. These are local validation failures. Accepted rows have local source-ID, source-hash, and evidence-span checks; that does not establish semantic correctness.

## Measured spending and throughput

| Scope | Jev charge | DeepInfra charge | Combined charge |
| --- | ---: | ---: | ---: |
| First 5,000 | $0.174531378 | $0.065068805 | $0.239600183 |
| Next 5,000 | $0.170293284 | $0.102163555 | $0.272456839 |
| **Two checkpoints** | **$0.344824662** | **$0.167232360** | **$0.512057022** |

These are measured checkpoint charges, not total account spend. The shared ledgers also include earlier development work and unresolved full reservations. Cumulative exposure is **$0.368926362 / $0.60 Jev** and **$0.932431294 / $5 OpenRouter**. OpenRouter exposure includes the older $0.024903544 hold and the two new holds totaling $0.011091968. A missing provider receipt is not evidence of zero charge. No credits were added and no cap was changed.

The next checkpoint used 3,999 new Jev calls. Its evidence stage saved 376 successful, 39 partial, one charged malformed, and two uncertain ten-review requests. The 416 metered evidence requests used 578,005 input and 475,161 output tokens, including 254,445 reasoning tokens. Their saved request durations sum to 12,343.812 seconds; mean 29.531 and median 25.29 seconds. Jev request durations sum to 1,686.982 seconds. These sums are request time, not elapsed wall time; the queue ran at most two workers.

## Semantic review and private handoff

An independent, model-assisted review of the pre-tail first-500 frame sampled 100 deterministic random accepted rows and 20 distinct risk rows. It made 44 findings across 39 source IDs: 14 about quote relevance, 18 about entity specificity, and 12 about label consistency. Every finding requires human review. This sample gives no human or golden accuracy rate. The four later tail rows were outside that audit frame. The private cumulative export retains saved labels and evidence unchanged, attaches the findings to the 39 affected records, and marks those records ineligible as representative evidence while the findings are open. Unflagged rows have not thereby passed human review.

The ignored, mode-0600 private handoff is `local/cumulative10000_dashboard_handoff.json`, SHA-256 `857dc1b50612fe5fe49f4ee4a9b2efcdeaa8bf5db492a53ef34f0e9873a5e203`. It contains 9,566 accepted records with original source fields, IDs, hashes, saved labels, exact evidence, and provenance, plus 434 excluded IDs and reasons. Its topic counts and severity sums are descriptive only; they are not issue grouping, ranking, or a recommendation. No review text, source ID, or private path is included in this report.

## Scale decision

**Do not start 100,000 reviews yet.** The next-5,000 measured mix projects roughly **$3.406 Jev plus $2.043 DeepInfra** for 100,000 source rows if text length, exact-text reuse, response quality, and prices remain similar. This simple multiplication is a planning estimate, not a measured 100,000-row cost or approval. At the same throughput and two-worker limit, its saved request durations imply at least about **39 hours** of inference wall time if work is perfectly balanced, before queue, QA, outage, deployment, or recovery overhead. The current Jev cap has only $0.231073638 of headroom, far below this projection. OpenRouter headroom is $4.067568706, but that is a ceiling, not permission to spend.

Before scale: obtain provider account or support evidence for the three uncertain requests while retaining their holds; review semantic flags and structural quarantines; measure and authorize a scaled budget; verify live route, prices, access, ten-review quality, and deadline schedule; and complete the required group, verifier, memo, backend, database, and deployed dashboard gates. The instructor's reported 100,000-row minimum differs from the unchanged full-corpus grading contract, so confirm final grading scope. No human golden labels were read or generated. No branch was pushed.
