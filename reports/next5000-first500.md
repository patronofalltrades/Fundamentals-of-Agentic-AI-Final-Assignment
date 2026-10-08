# Next 5,000 selection: first 500 gate

## Scope and provenance

The source selection is the 5,000 rows at positions 5,001–10,000 in the supplied Spotify CSV. The first gate is positions 5,001–5,500 only. The frozen selection manifest SHA-256 is `af6ecd58824d55cdeeca272f4cb6f1a86a1d6134cf90aa0981e7349b415c9722`. All selected source IDs, six original fields, row hashes, and exact-text hashes remain in the ignored local manifest. This report contains no review text or source ID. No human golden-answer file was used.

Jev used the existing `jev-1.13.0` rubric and configuration. Evidence used the revised exact-span prompt from the earlier 100-review recheck: `openai/gpt-oss-120b` pinned to `deepinfra/bf16`, ten distinct source texts per request, strict JSON schema, no fallback, `data_collection: deny`, and ZDR. The pinned route and project key were checked before inference. Only the first 500 selected rows were eligible; the remaining 4,500 were not processed.

The shared atomic ledger retained its earlier charges and its unresolved `$0.024903544` OpenRouter reservation. There were at most two new requests in flight. Each new request reserved the full token bound before network I/O. No provider account or credit setting changed.

## Measured outcome

| Metric | First-500 result |
|---|---:|
| Distinct source IDs accounted | 500 |
| Jev labels saved | 500 (403 new, 97 exact-text cache) |
| Evidence accepted | 494 (438 direct, 30 same-checkpoint exact-text cache, 26 compatible pilot cache) |
| Evidence quarantined | 2 (one quote exact-substring failure, one entity span failure) |
| Evidence pending | 4 distinct texts in the ten-review batch tail |
| New uncertain or active requests | 0 |
| Jev requests / new charge | 403 / `$0.017157966` |
| DeepInfra requests / new charge | 44 / `$0.010859795` |
| Combined measured new charge | `$0.028017761` |
| Jev cumulative exposure / cap | `$0.215791044` / `$0.60` |
| OpenRouter cumulative exposure / cap | `$0.830035566` / `$5.00` |

The 44 DeepInfra batches settled as 42 wholly valid and two partially valid. They used 60,925 input and 50,621 output tokens, including 27,274 reasoning tokens. Their summed request latency was 1,168.952 seconds; mean 26.567 seconds, median 23.906 seconds. The 403 Jev requests used 408,523 input and 79,183 output tokens; summed request latency was 402.198 seconds, mean 0.998 seconds, median 0.728 seconds. Saved Jev raw responses retain any provider-supplied confidence or probability details; the normalized four confidence values remain provider-reported values, not calibrated correctness probabilities.

The private ignored QA pack contains all 500 original source records, labels, evidence, request responses, costs, and status reasons. It was written with mode `0600` and has SHA-256 `d28a85ef88d515025236ce448a0c1fd97754f78de4c8af433f1402501a8b4e1f`. Offline QA verified every accepted quote/entity against its own exact source text and every selected source row hash. This is structural validation, not a semantic or human accuracy score.

## Interruption and gate

The evidence runner paused after 37 batches when a historical budget ledger became an iCloud `dataless` placeholder. Both in-flight requests settled before the pause. The historical files were hydrated locally, their SQLite integrity and the frozen shared-budget state passed, and only the remaining eligible batches resumed. No request was retried and no reservation was waived.

The first-500 gate is paused for quality review. Four pending distinct texts cannot form a ten-review request within this gate; they can join a later approved ten-review batch if the broader 5,000-row stage resumes. The two quarantined rows retain their saved provider responses and have not been retried. The 494 accepted rows require independent semantic review before issue grouping or product recommendations. This checkpoint does not demonstrate 100,000-row readiness or resolve the older uncertain DeepInfra charge/delivery.
