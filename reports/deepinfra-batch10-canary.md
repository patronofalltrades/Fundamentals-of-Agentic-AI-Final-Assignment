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

**Quality hold:** Against saved Codex development evidence, exact quotes
matched on **4/10** rows and entity lists on **0/10**. This is agreement with
a development baseline, not human truth. A manual spot check found several
batch quotes relevant to their supplied labels, but the model frequently
listed ordinary words, adjectives, or verbs as entities. The v1 batch prompt
requires exact source substrings and arrays but does not narrow entities to
named products, features, plans, or problems as clearly as the single-review
prompt. Exact-span validation catches invented text, yet it cannot reject
irrelevant exact words. The ten-row result does **not** support scaling this
batch prompt to 100,000 reviews. A stricter prompt and versioned cache need
another bounded quality check before any bulk authorization.

This one request measures batch token use and latency; it does not establish
parallel throughput, retry behavior in live failures, end-to-end cost, or a
100,000-row budget. The supplied grading contract still describes the full
660,622-ID output despite the instructor's reported 100,000-row minimum.
