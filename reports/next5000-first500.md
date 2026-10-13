# Next 5,000 selection: first 500 gate

## Scope and provenance

The source selection is the 5,000 rows at positions 5,001–10,000 in the supplied Spotify CSV. The first gate is positions 5,001–5,500 only. The frozen selection manifest SHA-256 is `af6ecd58824d55cdeeca272f4cb6f1a86a1d6134cf90aa0981e7349b415c9722`. All selected source IDs, six original fields, row hashes, and exact-text hashes remain in the ignored local manifest. This report contains no review text or source ID. No human golden-answer file was used.

Jev used the existing `jev-1.13.0` rubric and configuration. Evidence used the revised exact-span prompt from the earlier 100-review recheck: `openai/gpt-oss-120b` pinned to `deepinfra/bf16`, up to ten distinct source texts per request, strict JSON schema, no fallback, `data_collection: deny`, and ZDR. The final four-review tail used a separately versioned four-item schema with the same prompt, model, route, privacy controls, and full reservation. The pinned route and project key were checked before inference. Only the first 500 selected rows were eligible; the remaining 4,500 were not processed.

The shared atomic ledger retained its earlier charges and its unresolved `$0.024903544` OpenRouter reservation. There were at most two new requests in flight. Each new request reserved the full token bound before network I/O. No provider account or credit setting changed.

## Measured outcome

| Metric | First-500 result |
|---|---:|
| Distinct source IDs accounted | 500 |
| Jev labels saved | 500 (403 new, 97 exact-text cache) |
| Evidence accepted | 498 (442 direct, 30 same-checkpoint exact-text cache, 26 compatible pilot cache) |
| Evidence quarantined | 2 (one quote exact-substring failure, one entity span failure) |
| Evidence pending | 0 |
| New uncertain or active requests | 0 |
| Jev requests / new charge | 403 / `$0.017157966` |
| DeepInfra requests / new charge | 45 / `$0.010963931` |
| Combined measured new charge | `$0.028121897` |
| Jev cumulative exposure / cap | `$0.215791044` / `$0.60` |
| OpenRouter cumulative exposure / cap | `$0.830139702` / `$5.00` |

The 45 DeepInfra batches settled as 43 wholly valid and two partially valid. The first 44 carried ten reviews each; the final batch carried the four untouched tail reviews and passed all four source-ID and span checks. Together they used 61,603 input and 51,086 output tokens, including 27,508 reasoning tokens. Their summed request latency was 1,178.755 seconds; mean 26.195 seconds, median 23.891 seconds. The 403 Jev requests used 408,523 input and 79,183 output tokens; summed request latency was 402.198 seconds, mean 0.998 seconds, median 0.728 seconds. Saved Jev raw responses retain any provider-supplied confidence or probability details; the normalized four confidence values remain provider-reported values, not calibrated correctness probabilities.

The updated private ignored QA pack contains all 500 original source records, labels, evidence, request responses, costs, and status reasons. It was written with mode `0600` and has SHA-256 `58de22ba216db099af8adb2f7ac23fef859fc713bb336f90536c3a31dd9bd624`. The earlier pack remains unchanged as a before-tail snapshot. Offline QA verified every accepted quote/entity against its own exact source text and every selected source row hash. This is structural validation, not a semantic or human accuracy score.

## Interruption and gate

The evidence runner paused after 37 batches when a historical budget ledger became an iCloud `dataless` placeholder. Both in-flight requests settled before the pause. The historical files were hydrated locally, their SQLite integrity and the frozen shared-budget state passed, and only the remaining eligible batches resumed. No request was retried and no reservation was waived.

The first-500 gate is paused for quality review. The two quarantined rows retain their saved provider responses and have not been retried. The 498 accepted rows require independent semantic review before issue grouping or product recommendations. This checkpoint does not demonstrate 100,000-row readiness or resolve the older uncertain DeepInfra charge/delivery.
