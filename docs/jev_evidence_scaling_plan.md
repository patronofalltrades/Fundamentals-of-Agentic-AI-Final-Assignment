# Jev evidence route: bounded engineering plan

**Status:** Design and offline sizing only, October 6, 2026. No new model call,
installation, download, credential change, or large-scale execution was made.
The saved 500 classifications and their Codex evidence remain the comparison
reference, not human truth. The [checkpoint report](../reports/checkpoint-500-readiness.md)
and its readiness limits are unchanged.

**Prototype follow-up:** An offline generator and a held-out development
diagnostic are recorded in [the candidate prototype report](../reports/jev-evidence-candidate-prototype.md).
Its current cap rejects too many reviews, so the paid pilot gate is closed.

## Why this route needs a pilot

The current [`codex_evidence.py`](../spotify_pipeline/codex_evidence.py) starts
one Codex CLI process for each distinct review. The 379 new checkpoint calls
accumulated 2,567.54 seconds of successful request time. Jev's existing
[`jev.py`](../spotify_pipeline/jev.py) sends one review per label request and
accepts `choice` and `score` answers. Its 379 new calls accumulated 125.41
seconds of request time. These times describe different tasks and do not
predict evidence quality or throughput.

[TypeSafe's extraction example](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook)
requires code to find possible spans first; Jev selects from those spans.
[Choice and Noul](https://docs.typesafe.ai/primitives) return typed judgments,
not generated text. Choice names one winner and its option probabilities sum
to one. Independent Noul questions can judge multiple entity candidates in
one request. Questions in one request share the state but cannot depend on
one another. A Choice has at most 255 options. The candidate list must be
built and bounded in code.

## Separate versioned adapter

1. Read each original review from the existing source record. Keep its ID,
   source hash, text, frozen `jev-rubric-v2` labels, and cache origin intact.
   Never read human answer columns. Save a new evidence configuration such as
   `jev-candidate-evidence-v1`; do not overwrite the Codex evidence ledger.
2. Generate possible entity and quote spans locally. Store each with a stable
   candidate ID and exact Python string offsets into the original text. Use
   Unicode letter, number, and mark boundaries for entities, preserve case and
   punctuation, and add explicit handling for scripts without spaces and
   punctuation-bearing product names. Include the whole review as a quote
   candidate when nonempty. Split other quote candidates at sentence and
   clause boundaries and make short overlapping windows. Set explicit caps,
   initially **32 entity candidates and 16 quote candidates** per review;
   record `candidate_truncated` when either cap drops any candidate. Keep the
   generator deterministic and versioned. Do not claim multilingual recall
   until separately checked on multilingual development reviews.
3. Send one evidence-only Jev request per distinct uncached text. The `state`
   is the original review and frozen predicted labels. One Choice question
   selects a quote candidate ID or `none`. One independent Noul question per
   entity candidate asks whether that exact span names a relevant product,
   feature, plan, or problem. An independent Noul can ask whether the review
   contains any support for the saved labels. It cannot judge the selected
   quote after the Choice within the same request. The request carries no golden labels, Codex
   evidence, raw CSV, or credentials in model text. Keep the existing label
   request unchanged for this pilot. A later combined label/evidence request
   would need its own configuration and measured comparison.
4. Accept only returned candidate IDs and finite, in-range Noul values. Map
   selected IDs to original offsets in code. Recheck exact substrings and
   Unicode-aware whole-word entity boundaries with
   [`validate_evidence`](../spotify_pipeline/codex_evidence.py). Deduplicate
   entity spans in source order and cap accepted entities at ten. Preserve all
   raw selections, usage, timing, model version, request ID, and failures in
   the separate ledger. Treat a quote `none`, an invalid ID, a negative
   whole-review support judgment, an entity overflow, or a source mismatch as an evidence failure or
   abstention. Do not turn it into a completed classification. An empty entity
   list is allowed; record why it is empty. Evidence uncertainty must have a
   separate flag and must not silently change the saved label `needs_review`.
   Exact-source validation is mechanical; whether a selected quote actually
   supports the labels still needs a development review sample.
5. Reuse a saved evidence result only for exact identical text under the same
   candidate generator, question, model, and schema versions. Preserve the
   direct source ID and original provider provenance. The 500 completed Codex
   records are comparison material, not a cache hit for this new route.

## Offline sizing on the same 100 development texts

I read only the 100 saved v2 development review texts and saved Codex evidence
from the ignored local ledger. No text or original ID is copied into this
report. A disposable standard-library sketch generated distinct Unicode
one-to-three-word spans, sampled at most 32 across the text, and made at most
16 whole-review, clause, and short-window quote candidates. It constructed
one quote Choice plus one Noul per entity candidate. This is a *rough first
candidate generator*, not the proposed final implementation.

| Offline quantity | Result |
| --- | ---: |
| Review characters / word spans | 8,042 / 1,528 total |
| Entity / quote candidates | 1,943 / 437 total |
| Entity candidate cap exceeded | 39 of 100 reviews |
| Maximum questions in one request | 33 |
| Serialized request bytes | 439,081 total; 4,391 mean; 8,629 maximum |
| Rough bytes-divided-by-four input proxy | 109,770 tokens total |
| Price applied to that proxy | about $0.00461 for 100 calls |
| Exact overlap with saved Codex entity spans | 46 of 93 |
| Exact overlap with saved Codex quotes | 57 of 100 |

The token and charge proxies are **not measured Jev usage**. UTF-8 bytes are
not tokenizer counts, and server-side accounting may differ. The Codex
overlap is an agreement diagnostic, not recall against human answers or an
accuracy score. A full-review candidate is always available, but selecting
it does not prove that it supports the saved labels. The low entity overlap
shows that this naive generator is **not ready for paid comparison**. Build
the punctuation and multilingual candidate cases, then inspect aggregate
coverage and cap losses on this same fixed 100 before spending. Do not tune
against human golden answers.

## Bounded 100-review pilot gate

Freeze the improved generator, questions, span rules, and acceptance policy
before live calls. Run synthetic tests for Unicode boundaries, overlapping
spans, repeated text, full-review fallback, no candidate, too many candidates,
bad IDs, malformed Noul values, source drift, timeout and unknown delivery,
and direct/cache provenance. Run a read-only candidate audit on the 100 texts;
publish aggregate coverage against saved Codex spans and language/cap flags.
If coverage is still poor, stop and improve candidate discovery offline.

If the offline gate passes, use a separate ignored ledger for at most 100 new
evidence requests on `cost_100.csv`. Do not reuse the prior Codex output as an
input. Compare exact-span validity, quote abstentions, entity agreement,
coverage flags, per-request input/output tokens, billed cost, failures,
attempts, and wall time with the saved Codex reference. Have a human inspect a
small development disagreement sample without reading golden answer columns.
These are development judgments, not accuracy, macro F1, or a substitute for
the eventual frozen 50-case human evaluation. Keep the full pipeline gates in
the checkpoint report open.

The current [TypeSafe model page](https://docs.typesafe.ai/models) lists
`jev-1.13.0` at **$0.042 per million input tokens**, with free outputs, a
64,000-token total request limit, and a 32,000-token limit for state plus the
longest question. The rate and access must be checked again at launch. The
current measured cumulative v1/v2/checkpoint Jev spend is **$0.024101700**.
At the published rate, one maximally billed 64,000-token request per review
for 100 reviews would add at most **$0.2688**, or **$0.292901700** cumulative.
Propose a **$0.30 cumulative hard stop** for this pilot, still inside the
existing $0.60 pilot ceiling. Reserve the full 64,000-token cost before each
call, even if the local byte proxy is far lower. Allow no automatic retry of
an attempt with unknown delivery or usage; account for it at the reservation
maximum until reconciled. Stop if price, model, credit balance, or context
limits differ from the verified values. This is a proposed cap, not a run or
new authorization for a larger sample.

The pilot needs the existing TypeSafe account access and API key. The earlier
Mac launcher used visible Terminal with secure hidden input supplied by the
user. If a fresh launch lacks authentication, open that documented launcher
and stop at its key prompt for the user to enter the existing key. Do not read,
copy, log, or persist the key. No OpenAI or Ollama route is needed for the Jev
pilot. Do not start 100,000 reviews on the basis of this design.
