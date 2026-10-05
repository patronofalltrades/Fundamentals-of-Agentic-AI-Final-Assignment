# Jev enrichment adapter and pilot gate

Status: adapter, persistent pilot ledger, and gated commands implemented with
synthetic checks. The supplied 100-review Jev label pilot, separately authorized
Codex evidence extraction, and offline classification import completed locally.
All 100 outputs pass structural source and evidence checks. Human agreement is
unmeasured. Model inputs use source review text only, never human golden answers.

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
output is rejected unless every entity is an exact whole-word source span
without edge whitespace and the nonblank quote is an exact source substring.
It uses a temporary working directory, an ephemeral
ChatGPT-auth Codex session, read-only sandbox, and JSON schema. The local
`codex login status` reports **Logged in using ChatGPT**. A single call on
invented text succeeded under standard sandbox escalation with model
`gpt-6.1-sol`, schema output, and exact-quote validation. No assignment review
or golden answer was sent. The adapter does not invent entities
or quotes from Jev labels. The existing SQLite state validator checks exact
quotes again when a complete record is saved. The saved 100-review pilot was
imported into a separate ignored canonical classification database offline.

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

Before any further paid run, reverify the pinned model, current rate, account
route, and explicit cap. The existing 100 labels are settled; offline replay
must not repeat those calls. The offline `spotify_pipeline.jev_import` integration
builds complete records only after all 100 rows have labels and evidence,
checks every ID, text, and row hash against the canonical source database,
and imports direct originals before cache copies through the existing state
validator. The import ran on the saved 100-review pilot in a separate ignored
database. Its local attempt ID is a correlation ID, not a TypeSafe response ID.
Evidence semantic accuracy, token usage, and cost are unmeasured. The original
cold wall time remains unknown. Measure end-to-end warm behavior, and a fresh
cold run only if separately approved, before proposing 500, 10,000, or
full-corpus execution.

## Actual 100-review label pilot

The user entered the already configured TypeSafe key privately in a visible
Terminal window. The pinned source sample and manifest passed preflight, and
the read-only model-list access check passed. The runner used existing TypeSafe
credits with no top-up or fallback. Its ignored local ledger is
`local/jev_pilot.db`; no key is stored there. Offline replay and a separate
source-row comparison verified all 100 saved IDs, texts, row hashes, and the
configuration. All 100 Jev label responses passed enum, score, confidence,
usage, and pinned-model validation.

| Measured or recorded item | Result |
| --- | ---: |
| Direct label results | 100 |
| Settled attempts / retries / uncertain attempts | 100 / 0 / 0 |
| Returned input / output tokens | 87,887 / 19,656 |
| Sum of request elapsed time | 42.076869542 seconds |
| Usage-derived input cost at USD 0.042/M | USD 0.003691254 |
| Approved cap | USD 0.60 |
| `needs_review` by declared rule | 73 |
| Topic `other` | 47 |
| Evidence records / completed sample classifications | 100 / 100 |
| Exact source evidence validated / entity mentions | 100 / 93 |
| Evidence prompt versions | v1: 90; v2: 10 |
| Sum of evidence attempt elapsed time | 927.694823499 seconds |
| Offline read-only warm replay | 100 items, 0 model calls, 0.002301875 seconds wall time |

The account's actual credit debit was not independently checked. Total cold
wall time was not persisted, so summed request time must not be presented as
wall time. Evidence attempt time is also a sum, not evidence wall time. The
offline warm replay read the saved ledger and source database twice; its first
pass took 0.005421209 seconds and its warm pass 0.002301875 seconds. It made
no model calls by construction and does not replace an end-to-end warm pilot.
The local label distribution is not an accuracy result. No golden answers were
used for prompts or tuning. See aggregate-only `reports/jev-pilot-100.json`
for the measurement and limits.

Automatic approval review **rejected** an earlier separate Codex evidence
action as an external disclosure: it said the then-available instruction
prohibited uploading data and TypeSafe pilot approval did not cover that
service. No source review was sent to Codex during that rejected action. A
later user authorization enabled the saved 100-review evidence extraction.
The evidence and offline import now pass structural checks, including the
[entity boundary repair](jev_entity_boundary_bug.md). Semantic accuracy,
end-to-end warm measurement, and human agreement remain pending. Do not
expand beyond the 100-review pilot without the required gates.

The recorded pilot worktree stored no `.env` for the run.
A separate Desktop checkout has a nonblank TypeSafe key entry. Its existing
`src/labelling/smoke_typesafe.py` launcher can read that file for its own
demo smoke test without copying or printing the key, but it does not launch
this worktree's pilot runner. The key value was not read, copied, or used here.
The completed label pilot used the existing
`/Users/haniframadhan/Desktop/Fundamentals-of-Agentic-AI-Final-Assignment/.env`
locally. Hanif copied only the `TYPESAFE_API_KEY` value into a hidden prompt;
the variable existed only in the subshell and pilot process. No key was pasted
into chat, a command line, or a new file. The following records the launch
method for audit. **Do not rerun it now:** the 100-review label pilot is already
complete, and no second paid process should be started.

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
