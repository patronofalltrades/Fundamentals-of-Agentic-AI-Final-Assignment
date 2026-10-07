# DeepInfra ten-review canary: measured result

The first canary sent **ten distinct development reviews in one request** to
`openai/gpt-oss-120b` pinned to `deepinfra/bf16`. It used the corrected
development labels, prompt `deepinfra-batch10-evidence-v1`, strict structured
output, low reasoning effort, no fallback, data-collection deny, and ZDR
requested. The output limit was 4,096 tokens including reasoning. This is a
diagnostic evidence extractor, not a full classification or human evaluation.

| Measure | Observed |
| --- | ---: |
| Requests / source rows / accepted rows | 1 / 10 / 10 |
| Failed or retried requests | 0 |
| Input tokens | 1,368 |
| Output tokens, including reasoning | 1,034 |
| Reported reasoning tokens | 355 |
| Usage-derived charge | $0.000226396 |
| Request duration | 15.129 seconds |
| Full pre-call reservation | $0.024903544 |

All ten saved source IDs were distinct. Their original source hashes, returned
IDs, and exact quote and entity spans passed offline validation. The batch
saved atomically in the ignored ledger. There were no cache hits among these
ten distinct texts. Earlier single-review benchmark exposure remains held;
the combined local exposure after this settled canary is **$0.726093792**.
The later user-approved project cap is $5; this call occurred under the
earlier $1 local cap, and that history is retained.

**Quality finding:** Against saved Codex development evidence, exact quotes
matched on **4/10** rows and entity lists on **0/10**. These are development
agreement counts, not human accuracy. All ten batch quotes were exact source
spans; the reviewed complaint quotes generally supported their supplied
labels, though a few were broader or less focused than the Codex choice.
Entity differences included reasonable phrase granularity and omissions as
well as a clear error pattern: the batch often listed isolated ordinary
words, adjectives, or verbs instead of product, feature, plan, or problem
names. Even the two short general-criticism reviews received entity lists
where the saved Codex evidence used empty lists. The v1 batch prompt asked
for exact substrings but omitted the single-review prompt's semantic
restriction to products, features, plans, and problems. Exact-span checking
cannot catch irrelevant *exact* words. This proves a prompt mismatch and
supports a versioned v2 wording test; it does not prove every batch result
semantically unusable. The v1 result and cache identity remain preserved.

A mechanical straight-line projection from this one request is **$2.263960**
and **42.0 hours of summed request time** for 100,000 reviews in ten-review
requests with one worker, before failures, cache reuse, verification, grouping,
memo, queue overhead, and fixed costs. It is an illustrative rate, not a
forecast or spending approval. Review lengths and the v2 prompt may change
token use; two workers' wall time was not measured. Full endpoint reservations
could stop a run well before the $5 local cap even when expected bills are low.

This one request measures batch token use and latency; it does not establish
parallel throughput, retry behavior in live failures, end-to-end cost, or a
100,000-row budget. The supplied grading contract still describes the full
660,622-ID output despite the instructor's reported 100,000-row minimum.
