# First 5,000 source reviews: paused checkpoint

Measured on 2026-10-08 UTC. This is an interim development run, not the
instructor's clarified 100,000-source-review minimum or a full-corpus result.
The dataset and human golden answers were not changed or used for this report.

| Item | Saved result |
| --- | ---: |
| Selected source IDs and hashes | 5,000 |
| Jev-labeled source rows | 5,000 |
| Accepted evidence rows | 1,593 |
| Quarantined evidence rows | 36 |
| Pending evidence rows | 3,321 |
| Source rows in one uncertain request | 50 |
| Jev successful direct requests | 4,099 |
| DeepInfra successful or partial requests | 19 |
| DeepInfra uncertain requests | 1 |

The states sum to all 5,000 source rows. Exact-text caching retains each
source ID and source hash. The saved evidence spans passed local exact-source
validation. Structural QA found no source, membership, or provenance errors.
This is structural validation, not a human truth evaluation.

| Budget | Measured checkpoint charge | Historical exposure | Held reservation | Cumulative exposure | Cap |
| --- | ---: | ---: | ---: | ---: | ---: |
| Jev | $0.174531378 | $0.024101700 | $0 | $0.198633078 | $0.60 |
| OpenRouter | $0.013438407 | $0.726334928 | $0.024903544 | $0.764676879 | $5.00 |

Jev saved usage is 4,155,509 input and 805,251 output tokens across 4,099
direct requests. DeepInfra saved successful usage is 104,281 input and 56,353
output tokens, including 5,246 reasoning tokens, across 19 requests. These
totals exclude the uncertain request's unknown usage and charge.

One saved 50-review DeepInfra response repeated one source ID and omitted two.
Offline recovery accepted 47 uniquely identified direct rows and quarantined
the three ambiguous or missing direct rows, including their exact-text aliases.
The charged response was retained; no retry was sent. The runner then paused
after five consecutive batches contained one or more invalid exact-source
spans. After review and clean structural QA, a supervised resume used the same
batch size, route, workers, schema, and budget caps.

The resumed runner stopped on an uncertain 50-review response. It returned a
DeepInfra generation ID and `finish_reason=stop`, but had no usage fields and
no message content. Its measured charge is unknown. The full response and
request membership remain in the ignored local ledger, and the full
$0.024903544 reservation remains held. An authenticated, read-only OpenRouter
generation lookup returned HTTP 404 for this generation and a known successful
generation under the same key. This does not establish that the uncertain
generation was free. No further inference request or automatic retry is
permitted until provider activity or a receipt reconciles its charge and
delivery.
