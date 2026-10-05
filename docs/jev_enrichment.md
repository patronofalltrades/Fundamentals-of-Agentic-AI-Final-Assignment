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
`codex login status` reports **Logged in using ChatGPT**. A single call on
invented text succeeded under standard sandbox escalation with model
`gpt-6.1-sol`, schema output, and exact-quote validation. No assignment review
or golden answer was sent. The adapter does not invent entities
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
worktree has no usable key route. Before creating the ledger or making a paid
request, the runner makes a read-only `GET /v1/models` with the same key and
requires the `jev-latest` alias to be listed. The actual request remains pinned
to `jev-1.13.0` as documented by TypeSafe.
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
Hanif can open the existing
`/Users/haniframadhan/Desktop/Fundamentals-of-Agentic-AI-Final-Assignment/.env`
locally and copy only the `TYPESAFE_API_KEY` value. Do not paste it into chat,
the command line, or a new file. In a private zsh Terminal, run the following
from this worktree. The prompt hides the pasted value; the variable exists
only in the subshell and the pilot process, and shell history stores no key.

```sh
cd '/Users/haniframadhan/Documents/Codex/2026-10-05/task/jev-enrichment-worktree'
(
  read -s 'pilot_key?Paste existing TypeSafe key: '; print
  TYPESAFE_API_KEY="$pilot_key" python3 -m tools.jev_pilot \
    --input '/Users/haniframadhan/Desktop/Fundamentals of Agentic AI - Final Assignment - Spotify/Final Assignment - Spotify Reviews Dataset/cost_100.csv' \
    --manifest '/Users/haniframadhan/Desktop/Fundamentals of Agentic AI - Final Assignment - Spotify/Final Assignment - Spotify Reviews Dataset/manifest.json' \
    --execute --approved-cap-usd 0.60
)
```

The script records local labels and usage in the ignored
`local/jev_pilot.db`. It does not run the Codex evidence stage automatically.
The command checks model-list access before spending. Recheck the current
published price before running it; the assistant cannot perform an
authenticated account read without access to the key. No credential setup, billing change, top-up,
or paid fallback was performed. The first synthetic Codex check failed under
the ordinary workspace sandbox because its existing `~/.codex` state database
was read-only; the normal `require_escalated` approval path succeeded on retry.
No security settings or auth files were changed.
