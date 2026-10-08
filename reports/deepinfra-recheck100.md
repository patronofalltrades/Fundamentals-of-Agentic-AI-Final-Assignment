# DeepInfra 100-review evidence recheck

Measured on 2026-10-08 UTC. This is a development repair pilot, not a golden
answer evaluation or a representative estimate for all Spotify reviews. It
changed the evidence prompt and batch size together, from 50 to 10 reviews
per request. The result cannot isolate which change caused an improvement.
The original 5,000-row checkpoint and dashboard handoff were not modified.

The frozen private sample contains 100 distinct source IDs and exact texts:
50 hash-selected previously accepted rows, 25 previous exact-quote failures,
and 25 previous entity-span failures. Each 10-review batch mixes these strata.
All 66 uncertain source IDs and their exact texts were excluded. The sample
contains the saved prior outputs and validation reasons. Its canonical JSON
SHA-256 is
`5ae742b266401af25f441360d0be69f02de5f6338ded1f82274b9aba7e0681d5`.
The new configuration SHA-256 is
`54f07f7fdc1f6b52e5fd3e6f3ac42871bf13337801f61caf7c8bba8eb0a37ef0`.
Private sample and response-review artifacts are ignored under `local/`.

| Frozen stratum | Selected | Previously structurally accepted | New accepted | New quarantined | New exact-quote failures | New entity-span failures |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Previously accepted | 50 | 50 | 49 | 1 | 0 | 1 |
| Previous quote failure | 25 | 0 | 23 | 2 | 0 | 2 |
| Previous entity failure | 25 | 0 | 22 | 3 | 0 | 3 |
| **Total** | **100** | **50** | **94** | **6** | **0** | **6** |

All ten requests returned the pinned `openai/gpt-oss-120b` model through
`deepinfra/bf16`: six batches passed all ten rows and four were partially
valid. Every batch returned ten uniquely matching source IDs. No batch was
structurally malformed, delivered uncertainly, or retried. All six rejected
rows failed the existing exact whole-word entity-span validator; the new
prompt did not eliminate that failure mode. Strict ID and span checks were
unchanged. Full raw responses, usage, row outcomes, and generation IDs are
saved in separate pilot tables in the ignored shared project ledger.

| Measure | Saved result |
| --- | ---: |
| Input tokens | 15,702 |
| Output tokens, including reasoning | 13,456 |
| Reasoning tokens within output | 7,933 |
| Measured OpenRouter charge for this pilot | $0.002868494 |
| Mean / median request time | 31.96 / 27.37 seconds |
| Range / sum of ten serial request times | 21.83–50.42 / 319.57 seconds |
| OpenRouter cumulative exposure before / after, including old held uncertainty | $0.816307277 / $0.819175771 |
| Jev cumulative exposure, unchanged | $0.198633078 |

Each request reserved the full published input bound plus the 4,096-token
completion limit, $0.005545984, before POST against the existing atomic
OpenRouter $5 project ledger. The previous $0.024903544 uncertain reservation
remains held. The key was read through the existing macOS Keychain item; no
credential, billing setting, top-up, provider, or fallback was changed.

An informal review of 12 deterministically selected new accepted cases found
possible quote-to-label specificity issues in four and generic or weak entity
choices in two. Some quote concerns appear to reflect the frozen Jev label,
which this evidence-only pilot did not relabel. These are reviewer judgments,
not measured accuracy. The private 100-row review pack is available for an
independent semantic audit. No human golden answers were used.

The bounded recheck improved exact-quote structure on this deliberately
biased sample, while entity validity and semantic relevance remain concerns.
Do not scale this configuration to 100,000 reviews yet. Any further prompt
repair or paid recheck needs a separate decision and authorization; the old
uncertain request must remain isolated until its charge is reconciled.
