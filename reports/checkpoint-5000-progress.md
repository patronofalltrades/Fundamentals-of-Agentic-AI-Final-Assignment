# First 5,000 source reviews: accounted checkpoint

Measured on 2026-10-08 UTC. This is a development checkpoint, not the
instructor's clarified 100,000-source-review minimum or a full-corpus result.
The dataset and human golden answers were not changed or used for this report.

| Item | Saved result |
| --- | ---: |
| Selected source IDs and hashes | 5,000 |
| Jev-labeled source rows | 5,000 |
| Accepted evidence rows | 4,649 |
| Quarantined evidence rows, including exact-text aliases | 285 |
| Uncertain evidence rows, including exact-text aliases | 66 |
| Eligible pending evidence rows | 0 |
| Source rows in one uncertain request | 50 |
| Jev successful direct requests | 4,099 |
| DeepInfra successful or partial requests | 83 |
| DeepInfra charged, wholly quarantined requests | 1 |
| DeepInfra uncertain requests | 1 |

The states sum to all 5,000 source rows. Exact-text caching retains each
source ID and source hash. The saved evidence spans passed local exact-source
validation. Structural QA found no source, membership, or provenance errors.
This is structural validation, not a human truth evaluation.
Accepted coverage is 92.98%; quarantined and uncertain shares are 5.70% and
1.32%, respectively.

| Budget | Measured checkpoint charge | Historical exposure | Held reservation | Cumulative exposure | Cap |
| --- | ---: | ---: | ---: | ---: | ---: |
| Jev | $0.174531378 | $0.024101700 | $0 | $0.198633078 | $0.60 |
| OpenRouter | $0.065068805 | $0.726334928 | $0.024903544 | $0.816307277 | $5.00 |

Jev saved usage is 4,155,509 input and 805,251 output tokens across 4,099
direct requests. DeepInfra saved successful or partial usage is 480,644 input
and 274,018 output tokens, including 39,332 reasoning tokens, across 83
requests. The charged, wholly quarantined response adds $0.000701917 and is
included in the measured charge above. The uncertain request's usage and
charge remain unknown. DeepInfra's 83 accepted or partial requests had 79.65
seconds mean and 72.52 seconds median elapsed time (22.13–154.88 seconds).
This is per-request latency; repeated quality-gate pauses prevent a clean
end-to-end throughput measurement.

One saved 50-review DeepInfra response repeated one source ID and omitted two.
Offline recovery accepted 47 uniquely identified direct rows and quarantined
the three ambiguous or missing direct rows, including their exact-text aliases.
The charged response was retained; no retry was sent. The runner then paused
after five consecutive batches contained one or more invalid exact-source
spans. After review and clean structural QA, a supervised resume used the same
batch size, route, workers, schema, and budget caps.

An earlier runner stopped on an uncertain 50-review response. It returned a
DeepInfra generation ID and `finish_reason=stop`, but had no usage fields and
no message content. Its measured charge is unknown. The full response and
request membership remain in the ignored local ledger, and the full
$0.024903544 reservation remains held. An authenticated, read-only OpenRouter
generation lookup returned HTTP 404 for this generation and a known successful
generation under the same key. This does not establish that the uncertain
generation was free. The user authorized processing untouched source rows
while this request stays isolated with its full reservation. The new explicit
deferral path preserves that hold, excludes all attempted source texts, and
keeps the same cumulative budget and two-worker limit. It does not retry the
uncertain request.

The first deferral resume sent no inference request because the pinned
`deepinfra/bf16` route had catalog status `-5`. A later anonymous catalog check
returned status `0`. Automatic approval review initially rejected the paid
resume because it lacked the main-thread approval context. The coordinating
agent supplied the exact user approval for processing the remaining 3,321
rows under the existing caps, excluding the uncertain 50. The same runner
was accepted on a single retry. No fallback or model substitution was used.

The runner paused repeatedly at its five-consecutive-batches-with-invalid-rows
gate. Each segment's invalid reasons were reviewed before continuing with the
same model, prompt, schema, and cap. In total, 234 direct rows were quarantined:
151 for a quote that was not an exact source substring, 51 for invalid entity
spans, 17 for missing source IDs, and 15 for repeated source IDs. One separate
charged 50-review response contained an unknown source ID, so offline recovery
rejected the whole batch; its one exact-text alias is also quarantined. The
unresolved request has 50 direct source rows and 16 exact-text aliases. All 66
remain uncertain, with its full reservation held. No attempted source text was
sent again. The final 17 rows once shown as pending were these blocked aliases;
read-only QA now attributes each alias to its original request. No eligible
pending row or in-flight reservation remains.

An ignored, local human audit pack was prepared from the 1,593 currently
accepted rows. It contains a deterministic hash-ranked random sample of 100
accepted source rows and six separate sets of ten risk cases: low Jev
confidence, `needs_review`, high severity, exact-text cached evidence, partial
batch provenance, and quarantined rows. The random frame digest is
`5fb675e7008399bcf36e03add02ea7b980760b7528fc73d099688255f7b1febe`.
The pack contains original review text and IDs and remains outside Git. It
supports a human audit of model outputs; it does not estimate golden accuracy.

An independent model-assisted review of this frozen pack found five likely
semantic issues and five uncertain judgments among the 100 random accepted
rows. Among 50 separate accepted risk cases, it found four likely issues and
four uncertain judgments. Ten quarantined cases had no accepted output to
score. Likely issues involved topic, intent, severity, and quote relevance.
These findings are review signals, not human agreement or golden accuracy.
The checkpoint configuration stayed fixed for comparability. The structural
failure rate and model-assisted audit signals block a recommendation to scale
this evidence configuration. Before a 100,000-review run, the team should
adjudicate uncertain cases, fix exact-quote and entity-span behavior, review
the severity and praise/request rules, and run a bounded recheck of any
targeted change. A separate 10-review payload benchmark and explicit paid-run
authorization are still required. This 5,000-row checkpoint does not satisfy
the instructor's 100,000-row minimum or the unchanged full-corpus checker.
