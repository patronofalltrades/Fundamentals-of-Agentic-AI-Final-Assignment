# Measured results and remaining evidence — 15 October 2026

## Focused follow-up to deployed PR #35

Base: `0034e20031a3719612503f7fe84d63fb96822c77`.
This follows the existing [25-item inventory](production-measurement-audit-2026-10-15.md),
not a new broad audit. The seven cards below still say **Partial** on production.
They all contain saved observations. None is an unrun experiment.

The local correction separates measurement from completion. Each says
**Measured**, with an always-visible notice above its sample and metrics.
It does not say Ready or complete. Scores, denominators, null values, known
charges, reservations, source hashes and original reports are unchanged.
Broader quality limits remain in the card's disclosure section.

| Exact production card title | Live status | Local notice and specific unresolved evidence |
|---|---|---|
| Labelling runs: cost, speed and reliability | Partial | **Historical error count unavailable.** 500 final outputs exist, but the checkpoint report did not save its schema/identity-error count. The missing cell remains null. |
| The 100,000-review run: estimate against measured | Partial | **Billing unresolved; Historical forecast gaps.** Known labels/evidence charge is $4.725972366. Charges for 46 calls are unknown. Evidence-cost and call-count forecasts were not saved beforehand. |
| Evidence extractor benchmark | Partial | **Attempt coverage incomplete.** DeepInfra attempted 100; Groq attempted 82 of 100, leaving 18 untouched. The 9 and 16 invalid responses are measured failures, not missing attempts. Human semantic accuracy is unmeasured. |
| Blind verifier, ten reviews per request | Partial | **Output coverage incomplete.** 980/1,000 valid; 20 missing. Topic/intent/severity/joint agreement is 793/901/837/648 of 980. This is model agreement. |
| Grouping as a recorded program stage | Partial | **Output coverage incomplete.** 580/600 valid; 20 missing. Exact/family agreement is 449/503 of 580 against the historical model map. |
| Changed model claims and prompt injection | Partial | **Auditor and paired coverage incomplete.** Label auditor: 90/100 outputs, missing seven changed and three unchanged claims. Blind paired comparisons miss two label and four issue outputs among the observed planted cases. Injection has 24 measured comparisons; it does not prove general resistance. |
| Separate verification run: cost and resume | Partial | **Billing unresolved.** 125 attempts have unknown charge; $0.373186624 remains held. 212/213 logical requests have a settled result. Zero resends of three initially settled requests is already measured. |

All seven can honestly show **Measured** with these notices using saved data
alone. This closes the ambiguous presentation, not the missing evidence.
The complete 50-case diagnostic and the existing complete benchmark cards
need no relabeling. Pipeline verification remains **sample only**, including
if all 1,000 sample outputs are eventually available.

## One bounded paid follow-up — approved, not executed

Hanif approved the paid scope and then explicitly approved sending these source
inputs to OpenRouter/Crusoe on 15 October at 23:08:14 UTC. This clears the
spending and data-sharing consent gates. It does not clear the project-headroom
gate below. No inference has run.

**One-time cap: US$0.38 additional known charges plus all unresolved reservations,
across every attempt and role combined.** Use existing OpenRouter credits only.
No top-up, subscription, credential, billing-setting or provider fallback change.

Every role uses the same explicitly pinned service and route:

- API service and billing: **OpenRouter**, `https://openrouter.ai/api/v1/chat/completions`.
- Inference provider: **Crusoe**.
- Model: **`openai/gpt-oss-120b`**; provider route **`crusoe/bf16`**.
- Low reasoning; ten reviews per request; `max_tokens: 4096` including reasoning;
  strict JSON schema; concurrency one.
- `only: ["crusoe/bf16"]`, `allow_fallbacks: false`, `require_parameters: true`,
  `data_collection: "deny"`, `zdr: true`.

| Role and purpose | Data sent to OpenRouter and Crusoe | Initial calls | Maximum retries | Maximum total attempts |
|---|---|---:|---:|---:|
| Blind verifier: fill 20 missing labels | The 20 frozen review texts, original IDs, rubric and schema. No Jev predictions or prior verifier answers. | 2 | 1 per batch = 2 | 4 |
| Grouping: fill 20 missing assignments | The 20 frozen review texts and original IDs; existing Jev label/evidence context; frozen 41-issue catalog. No historical assigned issue. | 2 | 1 per batch = 2 | 4 |
| Label auditor: judge 10 missing claims | The 10 frozen review texts and original IDs; rubric; existing machine claims (seven changed by code, three unchanged). The auditor does not receive which claims were changed. | 1 | 1 | 2 |
| **Combined** | **50 distinct source IDs; five frozen batches** | **5** | **5** | **10** |

No human answers, human decision columns, golden labels, credentials, or full CSV
are included. The claims shown to the auditor are model outputs/perturbations,
not human truth. No new injection, Jev, Groq or human20 run is included.

### Verified preparation and budget

At **22:48:44 UTC on 15 October**, anonymous catalog checks confirmed the route
was available, supported the required parameters, and was ZDR-listed, at
**$0.05 per million input tokens and $0.25 per million output tokens**.
Authenticated read-only checks confirmed the existing non-resetting $5 project
key and sufficient existing account credits for $0.38. Private balance details
stay outside Git. These checks grant no permission to spend.

Sources: [OpenRouter endpoint catalog](https://openrouter.ai/api/v1/models/openai/gpt-oss-120b/endpoints),
[ZDR endpoint list](https://openrouter.ai/api/v1/endpoints/zdr), and
[provider routing controls](https://openrouter.ai/docs/guides/routing/provider-selection).
Recheck price, access, route and privacy immediately before any approved call.
Stop if they differ; do not switch providers automatically.

For conservative admission, reserve the endpoint's full 131,072 input and
117,964 completion token bounds: **$0.03604460 per attempt**, even though the
request asks for only 4,096 output tokens. Ten such reservations total
**$0.36044600**, below the $0.38 hard cap. Measured usage may settle lower;
missing usage retains the whole reservation. No savings are assumed.

Read-only shared-ledger exposure is $2.889317771 OpenRouter and $3.320208108 Jev.
Adding the entire proposed $0.38 gives $3.269317771 OpenRouter, below its $5 cap;
Jev is unchanged. These API figures are not a complete project bill. Confirm
at least $0.38 of headroom under the **$49.99 project ceiling**, including old
coding costs and unresolved holds, before execution. A paid approval alone
does not resolve missing historical accounting.

The five request hashes were regenerated and matched the private allowlist.
All source texts are present. None of those 50 IDs has a valid output in its
target role. Saved rejected response records are not accepted outputs.
Frozen plan hash:
`797d89195ac3b918a4ff8fb4bc598ac5291b811377dc02bd7516c3af0b4ed599`.
Private allowlist hash:
`b8f2edb158e85aea2d725fbfc34926797ad8acd6e53a5599b86da71f2a1ea6c8`.
The allowlist remains mode 0600 and is not committed.

### Execution boundaries for the received approval

Use a new follow-up namespace and durable ledger, with the five-batch allowlist,
one worker and a maximum of two attempts per batch. The existing broad runner's
25-attempt policy is **not** authorized. No wholesale resume of its old queue.
Reserve atomically in the shared ledger before each call and preserve all old
holds, failures and valid outputs. Save each response, route, usage and validation
outcome; validate exact ID membership and schema before accepting a whole batch.

Retry at most once only after an explicit HTTP rejection or a fully metered
invalid response. Never retry a lost response, timeout or unknown delivery
automatically. Stop on an uncertain new outcome, route/price change, cap or
accounting failure. A new attempt for the historically uncertain batch is an
explicit follow-up under this approval; its old reservation remains.
Invalid results remain invalid. This cap cannot guarantee successful outputs.

### What successful execution would complete

1. **Blind verifier, ten reviews per request:** 1,000/1,000 sample outputs.
2. **Grouping as a recorded program stage:** 600/600 sample outputs.
3. **Changed model claims and prompt injection:** 100/100 label-auditor outputs
   and complete paired joins for the frozen 50 changed-label and 50 changed-issue
   cases, after recomputation. Existing issue-auditor and injection outputs stay.

Retain the original experiment and separately identify the follow-up provider,
date and counts. Recompute aggregates from validated outputs before changing
coverage notices; do not predict the resulting agreement/detection scores.
This does not prove human accuracy, complete billing or make pipeline Verify a
population-wide pass. Publication of any resulting changes needs separate approval.

**Scope covered by the received approval (not an execution instruction):**

> Authorize the five frozen follow-up batches above through OpenRouter to Crusoe
> `openai/gpt-oss-120b`, pinned to `crusoe/bf16`, with no fallback and ZDR enabled.
> Permit the described 50 source texts/IDs and machine context, without human
> answers. Allow at most ten attempts total, no more than two per batch, and a
> hard combined US$0.38 in new charges plus unresolved reservations, using existing
> credits once. Preserve old holds, enforce all project caps and stop on unknown
> delivery. No human20, production writes, push, merge, deploy or submission.

## Gaps that this proposal cannot close

The [read-only project-headroom check](project-headroom-preflight-2026-10-15.json)
accounts for $6.209525879 of shared API exposure, including old holds, the cost
pilot, golden-gap run and verification experiments. Do not add those runs again.
Existing project-scoped OpenCode metadata records $0.185894358; one Claude
cost-state record adds $1.643784. These coding figures are tool-reported costs,
not a complete provider invoice or an exhaustive history.

Accounted exposure totals **$8.039204237**, or **$8.419204237** after reserving
the entire new $0.38. The remaining allowance under $49.99 is **$41.570795763**.
There is no demonstrated shortfall, but the unaccounted-cost upper bound is
unknown. Before execution, obtain authentic records or a documented budget-owner
bound showing that all omitted costs fit within that allowance. This must cover
remaining historical coding and grouping/verifier/memo work and clarify which
subscription, hosting and local-compute costs belong to the project budget.
Do not infer zero from absent records, discard holds, or increase the ceiling.
The **new $0.38 cap applies only to this follow-up's charges and unresolved
reservations**, including retries. Old holds remain separately counted in the
cumulative project exposure above.

- **Provider billing receipts required:** the 46 main-run calls and 125 separate-run
  attempts with unknown charge. New model calls do not reconcile old invoices.
- **Unrecoverable from existing saved records:** checkpoint schema-error count,
  pre-run forecasts that were never saved, invalid cross-process wall timing,
  missing main-run checkpoint pair and unrecorded historical token usage.
  Only genuine old evidence could change this; a new experiment cannot.
- **Human labels required only for new accuracy claims:** semantic extractor
  quality, review-flag precision/recall, or independent production grouping
  accuracy. Human20 remains declined; no new labels are needed for these three
  model-comparison samples. Business impact needs real product outcomes.
- **Other scope:** 18 Groq reviews remain untouched. No Groq calls are proposed
  here. The full-corpus checker remains `review_required`; the 110,000 selection
  does not satisfy its unchanged 660,622-row scope.

## Local validation and publication boundary

Local changes only. No inference, production database write or publication.
The status correction changes no numerical metric or comparison value.

- Python: 431 tests ran, 429 passed and two skipped because their private fixture
  was absent. The suite used the required local socket permission.
- CLI help and evaluation-registry reproducibility check passed.
- Frontend build: two pages in 2.86 seconds. Typecheck: 36 files, zero errors,
  warnings or hints. Four Node tests passed.
- Frontend validation used the existing Node 26.8.2 runtime on this Mac, with
  780 pinned packages restored from the existing offline cache. All 47 source,
  configuration and static files matched the worktree. No package or lockfile
  changed. No network or install scripts were used for that restore.
- The original dependency tree stalled on synchronous file reads. A bundled
  alternate runtime rejected its native binding because of macOS library
  validation. No security protection was changed. The identical cached tree
  completed with the existing runtime.
- All numerical metrics, comparisons, samples, findings, decisions and source
  fingerprints matched the base registry. No missing evidence was filled.
- Local Chrome check: all seven affected cards showed Measured with visible
  notices outside collapsed details. Verifier 980/1,000, grouping 580/600 and the
  complete 50-case diagnostic stayed unchanged. No Ready claim appeared. An
  initial empty Evidence fixture lacked its total; fixing only that temporary
  fixture resolved its console error. No new errors appeared after reload.

The exact local commit/file list is in the completion handoff.
