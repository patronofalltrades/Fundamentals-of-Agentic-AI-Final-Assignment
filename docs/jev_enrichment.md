# Jev enrichment adapter and pilot gate

Status: offline adapter implemented and synthetic tests passed. No Jev review
request has been sent. No runtime classifications or real pilot measurements
exist. This design uses the source review text only. It must never use the human
golden answer file as an input or tuning target.

## Current documented interface and price

Checked October 6, 2026 against the official [quick start](https://docs.typesafe.ai/introduction/quickstart),
[Choice](https://docs.typesafe.ai/primitives/choice),
[Score](https://docs.typesafe.ai/primitives/score), and
[models](https://docs.typesafe.ai/models) pages. The API uses
`POST https://api.typesafe.ai/v1/systemone` with bearer authorization and a
`state`, `model`, and `questions` object. We pin `jev-1.13.0` so an alias cannot
silently change. The published input rate is USD **0.042 per million tokens**;
output tokens are free. The listed context limit is 64,000 tokens per request,
with a 32,000-token limit for state plus the longest question. Recheck the rate,
model, and account access before any paid run.

The adapter uses one source review per request. It sends four questions in that
request: topic and intent as Choice, severity as Choice among five separately
described integer labels, and sentiment as Score with five ordered tone
anchors. The Score's 0–4 output maps linearly to the assignment's −1 to +1
sentiment range. The original star rating, ID, app version, and human answers
are excluded from the model state. Review text is untrusted data, not an
instruction to the program.

`spotify_pipeline/jev.py` constructs requests and rejects an unexpected model,
unknown choice, out-of-range score, missing usage, or malformed confidence.
`needs_review` is true if any of the four confidence values is below 0.60, or
if the topic is `other` or intent is `unclear`. This threshold is a declared
pilot rule, not a calibrated accuracy guarantee. The versioned configuration
from `label_config()` fits the foundation's exact-text cache key, which
invalidates reuse when model, effort, prompt, or schema version changes.

Entity and evidence extraction is a distinct pending role. The adapter does
not invent entities or a quote from Jev's label output. Its
`combine_with_evidence()` requires an exact nonblank source substring before
it yields a classification payload. The existing SQLite state validator
checks this again when a complete record is saved. There is currently no
runtime runner connecting this adapter, extraction role, persistent budget
ledger, and database; therefore **do not execute paid calls with this adapter
yet**. A timeout is not retried because billing may have happened without a
received response. HTTP 429 and selected 5xx errors can retry once, with
bounded `Retry-After`; attempts and elapsed time are returned on success.
Failed or uncertain calls require a run journal before live use.

## Reproducible dry run on the supplied sample

From the Jev worktree root, using the newer course package:

```sh
python3 -m tools.plan_jev_pilot \
  --input '/Users/haniframadhan/Desktop/Fundamentals of Agentic AI - Final Assignment - Spotify/Final Assignment - Spotify Reviews Dataset/cost_100.csv' \
  --manifest '/Users/haniframadhan/Desktop/Fundamentals of Agentic AI - Final Assignment - Spotify/Final Assignment - Spotify Reviews Dataset/manifest.json'
```

The tool checks the supplied cost sample's SHA-256, bytes, six source columns,
100 unique IDs, and nonempty text. It prints aggregates only. The verified
sample has SHA-256 `c884ac3b9be5066995d5063f96ad9af6e5e082975788c1684c4f6b6ea661dd0e`.
It yields 221,738 UTF-8 bytes of serialized requests. Dividing bytes by four
gives an **illustrative** 55,434 input tokens and USD **0.002328228**. This is
not a tokenizer, bill, or runtime measurement. One request per review means
100 planned calls before retries, up to 200 attempts if every call hits the
single permitted retry. The published 64k context maximum implies a
conservative 200-attempt ceiling of USD **0.5376** at the listed rate. A
proposed pilot hard cap is **USD 0.60**, subject to user approval. It is a
proposal, not permission to spend. The global project ceiling is USD 49.99.

Before the live pilot, implement a persisted pre-call reservation and
post-call usage ledger. Reserve for the full possible billed context of each
attempt, check the approved cap before any call, record all attempts,
response model, `usage.input_tokens`, `usage.output_tokens`, elapsed time,
errors, and uncertain outcomes without storing secrets in logs. Reconcile
actual cost using the then-current published rate. Keep source IDs and texts
in ignored local state only. Use existing configuration-scoped SQLite state
for completed results and direct exact-text cache provenance. The cold and
warm 100-review runs must both be measured before proposing 500, 10,000, or
full-corpus execution. Keep an offline replay of the measurements and a
checkpoint; reopening either must make zero API calls.

The current shell has no `TYPESAFE_API_KEY`; the active worktree has no `.env`.
A separate Desktop checkout has a nonblank TypeSafe key entry, but its value
was not read, copied, or used. A live runner will need a secure key available
to its own process, and a harmless account/model read should succeed before
spending. No credential setup or billing change was performed.
