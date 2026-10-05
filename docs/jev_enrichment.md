# Jev enrichment adapter and pilot gate

Status: adapter, persistent pilot ledger, and gated commands implemented with
synthetic checks. No Jev or Codex review request has been sent. No real pilot
measurement or completed classification exists. Model inputs use source review
text only, never the human golden answer file.

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

Entity and evidence extraction is a separate, opt-in Codex CLI stage. Its
output is rejected unless every entity and the nonblank quote are exact
source substrings. It uses a temporary working directory, an ephemeral
ChatGPT-auth Codex session, read-only sandbox, and JSON schema. The local
`codex login status` reports **Logged in using ChatGPT**, but this route has
not been run on reviews, and its model availability and isolation behavior
have not been verified with a live call. The adapter does not invent entities
or quotes from Jev labels. The existing SQLite state validator checks exact
quotes again when a complete record is saved. A final import into that
canonical classification store remains a manual integration step.

The Jev pilot runner has a separate SQLite ledger in ignored `local/`. It
reserves the published 64k-token maximum, USD 0.002688, **before each attempt**
and refuses an attempt that would exceed the approved cap. A successful
response settles to `usage.input_tokens × 42` nanodollars; missing usage,
network failure, or a crash keeps the full reserve as uncertain spend. A
timeout is not retried because billing may have happened without a response.
HTTP 429 and selected 5xx errors can retry once, with bounded `Retry-After`;
each attempt has its own reservation and elapsed time. The ledger stores
source ID, text and row hash locally, with config and model identity. Reuse
requires exact text equality and a direct original; a cached row retains its
own ID and points to the direct source. Reopening the ledger with a different
sample, configuration, model or cap fails. Its replay is read-only and makes
no calls.

## Reproducible dry run on the supplied sample

From the Jev worktree root, using the newer course package:

```sh
python3 -m tools.jev_pilot \
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
pilot hard cap is **USD 0.60**, approved by Hanif for existing TypeSafe
credits only. No top-up or paid fallback is approved. The global project
ceiling is USD 49.99; this pilot cannot expand automatically.

The CLI defaults to that offline plan. Paid `--execute` requires an explicit
`--approved-cap-usd` no higher than 0.60, a key in the process environment,
and the pinned sample/manifest. Hanif has approved the limit, but this
worktree has no usable key route; verify account/model access before use.
After a run, `--replay` reads the
same ignored `local/jev_pilot.db` with no network. The separate
`python3 -m tools.jev_evidence` command defaults to an offline count of Jev
results missing evidence; its `--execute` option calls ChatGPT-auth Codex and
must be separately reviewed before use. No external call is made by importing
either module, running `--help`, planning, or replaying.

Before a real cold/warm pilot, verify the pinned model and rate for the account,
confirm the approved cap, and provide the existing key securely to this
process. Measure actual Jev usage, wall time, and failures. Then review the
Codex evidence route. The offline `spotify_pipeline.jev_import` integration
builds complete records only after all 100 rows have labels and evidence,
checks every ID, text, and row hash against the canonical source database,
and imports direct originals before cache copies through the existing state
validator. This import is implemented and synthetic tested but has not been
run on real data. Its local attempt ID is a correlation ID, not a TypeSafe
response ID. The evidence stage has no claimed accuracy or usage measurements.
Run and report both cold and warm 100-review measurements before proposing
500, 10,000, or full-corpus execution. No pilot ledger exists yet.

The current shell has no `TYPESAFE_API_KEY`; the active worktree has no `.env`.
A separate Desktop checkout has a nonblank TypeSafe key entry. Its existing
`src/labelling/smoke_typesafe.py` launcher can read that file for its own
demo smoke test without copying or printing the key, but it does not launch
this worktree's pilot runner. The key value was not read, copied, or used here.
Hanif must make the already configured key available to the pilot process
through an approved secure launcher or environment before execution. No
credential setup, billing change, top-up, or paid fallback was performed.
The Codex CLI reports ChatGPT login, but an isolated synthetic extraction
attempt failed before reaching the model because the execution sandbox could
not write its existing `~/.codex` state database. No synthetic answer was
returned. The Codex evidence stage also remains blocked until a supported
runtime permits that state access; do not copy its auth files or use an API-key
fallback.
