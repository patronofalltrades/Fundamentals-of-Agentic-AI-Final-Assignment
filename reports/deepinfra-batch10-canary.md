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

## Version 2 prompt trial

After Hanif approved the project key and its read-only check reported a normal
inference key with a non-resetting USD 5 limit and USD 5 remaining, the v2
prompt sent the **same ten development reviews** in one new request. It kept
the pinned DeepInfra route, strict schema, privacy settings, low reasoning
effort, output bound, and source checks. The v1 result remains in its own
ignored ledger. The v2 generation ID is
`gen-1791352720-kSSz1Cpx75euqaEBiEUR`.

| Measure | V1 | V2 |
| --- | ---: | ---: |
| Requests / accepted rows | 1 / 10 | 1 / 10 |
| Failed or retried requests | 0 | 0 |
| Input tokens | 1,368 | 1,408 |
| Output tokens, including reasoning | 1,034 | 1,112 |
| Reported reasoning tokens | 355 | 530 |
| Usage-derived charge | $0.000226396 | $0.000241136 |
| Request duration | 15.129 s | 14.524 s |
| Full pre-call reservation | $0.024903544 | $0.024903544 |
| Exact quote agreement with Codex development evidence | 4/10 | 3/10 |
| Exact entity-list agreement with Codex development evidence | 0/10 | 3/10 |

All ten v2 IDs, original source hashes, and distinct texts matched the
selected source rows. Every saved quote and entity passed exact source-span
validation, and the ten results committed atomically. There were no cache
hits, errors, or retries. The lower exact quote agreement reflects several
shorter, focused quotes; it is **not** a measured drop in quote quality.
Manual review found the complaint quotes generally relevant to their supplied
labels. The v2 instruction reduced isolated generic verbs and adjectives and
recovered several meaningful phrases. It still emitted entities for both
short general-criticism reviews where saved Codex evidence used empty lists;
one was a generic app noun and the other a rating phrase. Some other lists
omit named products or include broad music terms. Exact-list agreement is a
development diagnostic, not human accuracy or a gold evaluation.

Known charges plus unresolved historical reservations are now
**$0.726334928** across the historical single-review ledger and both canaries.
The v2 runner's pre-call cap calculation included the historical ledger and
v2 ledger, but omitted the already settled v1 canary ledger. The USD 5 cap
was not approached, yet this is an accounting gap. Include **all** prior
ledgers in a shared atomic cost ledger or equivalent fail-closed reservation
check before any further paid scaling. Do not treat the separate canary
ledgers as the final multi-worker accounting design.

One-request v2 arithmetic gives **$2.411360** of extractor API charges and
**40.35 hours of summed request time** for 100,000 reviews at ten per request.
This is an illustration only. Review length, failures, cache hits, parallel
throughput, verifier, grouping, memo, backend, and queue costs remain
unmeasured. The two short-review entity errors and absent human truth are
quality gates before a larger run. No 100,000-review run was authorized or
performed.
