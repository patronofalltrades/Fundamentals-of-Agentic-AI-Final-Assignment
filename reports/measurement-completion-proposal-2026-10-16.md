# Proposal: finish verifier and grouping coverage

**Approval recorded at 00:18:20 UTC, 16 October.** This document preserves the
scope proposed before approval. Execution results will be reported separately.

Goal: reach 1,000/1,000 valid verifier outputs and 600/600 valid grouping outputs.
Agreement with the prior model is not a condition for acceptance. Whole-batch
structural validation and exact source identity are required.

## Frozen scope and recipients

The local read-only preparation verified exactly 30 pending distinct original
source IDs: 20 verifier reviews and ten grouping members. They form three original
ten-review batches. No accepted result is included or overwritten.

Recipient chain: OpenRouter API, then **Crusoe `crusoe/bf16`**, using
**`openai/gpt-oss-120b`**. Concurrency is one. Use low reasoning, `max_tokens=4096`,
strict JSON schema, required parameters, no fallback, zero data retention and
`data_collection=deny`.

Verifier requests contain original IDs and review text plus the frozen rubric.
They do not contain first predictions. The grouping request contains original
IDs and text, saved machine labels and evidence quotes, plus the frozen issue
catalog. It does not include the old issue assignment. Human golden answers are
excluded from every request. The private manifest holds the exact payloads;
the public aggregate exposes only hashes and sizes.

Each response schema enumerates its ten exact input IDs. This changes the request
hash from the failed run. The original payloads and failed responses stay saved.
Returned rows must form an exact bijection with requested IDs. No positional or
similarity repair and no partial-batch salvage are allowed.

Manifest SHA-256:
`186397d8243b8dbe278949e503049ed1ef8c844f9adeb792c58a31e37655a9e3`.
The [machine-readable proposal](measurement-completion-proposal-2026-10-16.json)
contains the three request fingerprints and pending-set fingerprints.

## Attempts, timing and stop conditions

- Three batches; at most three attempts each, including two retries.
- At most nine total paid attempts. Successful batches are never repeated.
- Retry only explicit HTTP 429/5xx rejection or fully metered invalid output.
- Stop all work on uncertain delivery, route/privacy/price change, identity
  mismatch in the frozen inputs, authentication/configuration error, insufficient
  funds, active conflicting paid work, or a reservation/cap failure.
- Wait at least 45 seconds after every response before another request. For
  HTTP 429/5xx, use the greater of this delay and Retry-After seconds or HTTP date.
  Save rate headers and the next allowed time. Resume must honor that time.
- If the required wait exceeds 300 seconds, stop and retain the durable wait
  instead of dispatching. No retry may bypass that wait after restart.
- Persist request hashes, raw responses, validation failures, usage, charges
  and full unresolved reservations. Keep private outputs mode 0600 and ignored.

The 45-second interval is a conservative proposed policy, not a measured server
limit. It cannot guarantee success. Stop at either bound even if coverage is
still incomplete; another approval would then be required.

## Proposed allowance and preserved holds

The public route catalog was checked at **00:09:14 UTC, 16 October 2026**.
It lists US$0.05 per million input tokens and US$0.25 per million output tokens;
the required parameters and ZDR entry are present. Recheck before inference.
Source: [OpenRouter endpoint catalog](https://openrouter.ai/api/v1/models/openai/gpt-oss-120b/endpoints).

| Bound or saved exposure | US dollars |
| --- | ---: |
| Full conservative reservation per attempt | 0.036044600 |
| Nine full reservations: maximum new charges plus holds | 0.324401400 |
| Requested separate one-time ceiling | **0.330000000** |
| Existing shared OpenRouter exposure | 3.106732071 |
| OpenRouter exposure with all nine new reservations | 3.431133471 |
| Existing shared Jev exposure | 3.320208108 |

The per-attempt reserve uses the endpoint's full 131,072 input and 117,964 output
token bounds. It is deliberately larger than the 4,096-token request limit.
Every call requires an atomic reservation. Known metered charges use the larger
of reported cost and usage-derived cost. Uncertain charges retain the full hold.

The shared reservation table currently has 170 OpenRouter holds totaling
US$0.875240200 and eight Jev holds totaling US$0.021504000. The six prior follow-up
holds total US$0.216267600 and are already included in the OpenRouter figure.
Historical imported exposure is also included in each provider total; its
uncertain components are not itemized by this proposal. No old hold is released.
Both provider caps remain US$5.

The prior US$0.38 run exhausted its ten attempts. Its leftover allowance does not
authorize this run. Full historical project headroom remains unbounded because
some old costs are unknown. Approval must therefore explicitly grant this
**new separate one-time US$0.33 allowance**, as with the prior exception, and the
payload/recipient scope above. It does not increase any broader project cap.

## Readiness and approval boundary

The proposal command has no execute path. The separate
`tools/run_measurement_completion.py` now binds the complete manifest digest,
new namespace, three-batch/nine-attempt policy and recorded approval. Offline
checks verify every pending ID and request before execution. A fresh route,
credit, source-hash and shared-headroom preflight is still required. The
exhausted five-batch run and its original manifest remain unchanged.

This proposal excludes auditor, synthetic attack, golden scoring, product memo,
production database, release and grading changes. Publishing any aggregate
result still requires separate publication approval. No push, merge, deployment
or course submission is authorized here.
