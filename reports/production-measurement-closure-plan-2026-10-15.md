# Measurement closure and approval plan — 15 October 2026 UTC

## Ready for publication review

The frontend gate is now closed. The requested restore used only the existing
lockfile and `registry.npmjs.org`, with separate empty npm configuration files,
install scripts disabled, audit/funding calls disabled and a temporary cache.
It restored 780 applicable packages. No dependency, package version or lockfile
changed. Node 26.8.2 meets the repository requirement.

- `npm run build`: passed; both `/` and `/memo/` built in 13.13 seconds.
- `npm run typecheck`: 36 files, zero errors, warnings or hints.
- Existing local revision checks: 428 Python tests passed, two private-plan tests
  skipped; four Node tests passed. CLI, generated reports and privacy checks passed.
- Lockfile SHA-256 remains
  `6db7a0c31e9c59cc84aa8695ef80192e3200e81dc3d2632fbd742dd37c82db47`.

The recommended next step is to publish the reviewed code and aggregate reports.
**No production database import, membership replacement, golden rescore or memo
rewrite is needed.** `/api/summary` reads the saved registry and matches its
source/configuration to the current database. `/api/evals` serves that registry.
A normal application deployment picks up those changes. The old import manifest
remains a historical snapshot.

## Concrete approval choices

### A. Publish the completed local correction — recommended

Approval wording:

> Publish `feat/production-measurement-audit` to the existing GitHub repository,
> open a PR, and merge/deploy to the existing Vercel site after its checks pass.
> Include only the reviewed code and text-free aggregate reports. Do not import
> data into production, change the grading release, run inference or submit the
> assignment.

Destination: `patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment` and
`hanif-spotify-insights.vercel.app`. Payload: the 17 original changed files listed
below, plus this closure plan and its aggregate preflight evidence. No private
plan, source text, source IDs, answers, DB or npm cache is included. New inference
cost: $0. Existing hosting/billing settings are unchanged. This authorization has
**not** been given; nothing was pushed or deployed.

### B. Optional completion of the 20 verifier and 20 grouping outputs

Approval wording:

> Authorize a new, separately recorded follow-up for only the 40 frozen missing
> verifier/grouping rows, using OpenRouter → Crusoe `crusoe/bf16`, model
> `openai/gpt-oss-120b`. Maximum 8 new calls, at most one retry per ten-row batch,
> and at most US$0.30 additional known charges plus unresolved reservations.
> Preserve every historical hold and output. Keep fallback off and zero data
> retention on. Do not send human answers or change production data.

This is **optional for the published 100,229-row release**. It is necessary only
if we want all 1,000 verifier and 600 grouping sample outputs. Existing valid results
remain usable with observed denominators. No new human labels are required.
Completing these outputs still measures model agreement, not human accuracy.

### C. Optional completion of the label-auditor sample

The 20+20 option does not fill the separate ten-row auditor rejection: seven changed
labels and three unchanged labels remain missing. If full planted-audit coverage
is wanted, add one ten-row batch, at most one retry, maximum 2 calls and
**US$0.08 additional exposure** on the same Crusoe 120B route. Verifier/grouping plus
this auditor option therefore permits at most 10 calls and US$0.38 new exposure.
This is not required to publish the local correction.

### D. Optional Groq benchmark continuation — lower priority

The 18 untouched rows are needed only to finish the planned 100-attempt Groq arm.
The chosen production extractor and accepted 100k target do not depend on it.
The 25 old invalid responses are measured failures; retrying them is not required
to complete the original attempt-rate comparison and would alter that experiment.

A safe bounded approval would allow **at most 18 new single-review calls, zero
retries, and US$0.26 additional exposure** via OpenRouter → Groq `groq`, model
`openai/gpt-oss-20b`, on only the untouched frozen rows. Preserve the original
benchmark cap strictly below US$1; use a stricter cumulative US$0.99 stop gate.
This option may stop before all 18 attempts. Do not promise completion within it.

To guarantee headroom for all 18 full endpoint reservations instead, authenticated
billing evidence would first need to release **at least US$0.266708996** from the
old benchmark exposure. No hold is released in this task and no cap increase is
requested. Do not open a new ledger to evade the cumulative benchmark ceiling.

## Current route, source and cap evidence

[Preflight aggregate](production-measurement-preflight-2026-10-15.json) records
anonymous public catalog GETs at 21:03:50 UTC, source/hash checks, private-plan
coverage checks and local ledger arithmetic. Credentials and inference were not
used. Recheck catalog status, prices, required parameters, zero retention and
account access immediately before any approved dispatch.

| Proposed work | Available source and purpose | Maximum calls / retries | Conservative exposure bound |
|---|---|---|---|
|20 verifier outputs | Frozen plan hash matches the public report and DB. All 20 missing rows have text; original sample excludes 150 golden/pilot IDs. Verifier sees only text, IDs and rubric, never the first label. |2 ten-row batches; max 4 attempts, one retry per batch |Full endpoint reservation is $0.0360446 per attempt; 4×=$0.1441784. Share a $0.30 cap with grouping. |
|20 grouping outputs | Same frozen plan; all 20 texts and saved labels/quotes are present. Historical issue assignments stay hidden. |2 ten-row batches; max 4 attempts, one retry per batch |4×$0.0360446=$0.1441784. Both roles' bound=$0.2883568, below $0.30. |
|10 label-auditor outputs | Same frozen plan has the ten missing audit cases and changed/unchanged claims. These are model claims, not human answers. |1 ten-row batch; max 2 attempts |2×$0.0360446=$0.0720892; optional cap $0.08. |
|18 Groq extractor attempts | Cost 100 source has 100 distinct IDs and matches the frozen source hash. All 18 untouched texts are nonempty; saved baseline labels match source-row hashes. |Max 18 single-row attempts; zero retries |Full endpoint reservation=$0.0294912 each; 18×=$0.5308416. This exceeds the currently available old benchmark headroom. The $0.26 option stops before its cap. |

Crusoe 120B catalog prices are $0.05/M input and $0.25/M output, status 0, listed for
zero retention. Groq 20B is $0.075/M input and $0.30/M output, status 0, also listed.
DeepInfra 120B retains its old quoted prices but reports status `-2`; existing
preflight rejects it. Do not silently fall back or run it. Sources:
[120B endpoint catalog](https://openrouter.ai/api/v1/models/openai/gpt-oss-120b/endpoints),
[20B endpoint catalog](https://openrouter.ai/api/v1/models/openai/gpt-oss-20b/endpoints),
[zero-retention endpoint list](https://openrouter.ai/api/v1/endpoints/zdr).

The bounds reserve the full published 131,072 input token limit plus 117,964 output
tokens for Crusoe or 65,536 for Groq. They do not assume the requested 4,096/320 token
limit is a hard billing limit. Discounts and prompt caching are ignored.

The shared API ledger currently records OpenRouter exposure $2.889317771 and Jev
exposure $3.320208108, each against its existing $5 ceiling. The separate verification
run retains $0.413438403 exposure against its recorded $1.50 cap. The legacy extractor
benchmark retains $0.725867396 against its strict $1 cap. These overlap; **do not add
them as independent project bills**. The shared API ledger is not the complete
project bill: coding and unknown historical chat usage remain separate. Preserve
the overall $49.99 ceiling and verify the cost owner's complete admission evidence
before any paid execution.

If B, C and stop-limited D were all separately approved, their new caps total
US$0.64; this is not an authorization or a projected charge. Every unresolved
attempt retains its full reservation. A smaller actual charge is not assumed.

## Execution prerequisites; no paid runner was launched

1. Prepare a narrowly scoped follow-up runner and test it offline. The current
   `execute --resume` is unsuitable: it skips settled quarantines/held requests,
   can retry HTTP errors up to 25 times, and checks DeepInfra before dispatch.
   Do not disable those safeguards or run the whole 213-request plan.
2. Use the saved missing-row allowlist and frozen request hashes. A private
   mode 0600 proposal manifest is prepared; it contains five optional ten-row
   batches and no human answers. It is not a runnable authorization.
3. Preserve old ledgers. Use new attempt identities with explicit links to the
   original failed batches, reserve in the shared atomic ledger, and enforce
   both new subcaps and old cumulative caps. In particular, appending to the
   frozen legacy benchmark ledger would change its shared-ledger digest.
4. For the held verifier batch, first seek authentic billing/response evidence.
   The local ledger has no saved usable response for it; the other failed
   verifier batch and two grouping batches still fail the existing content
   validator. No free valid output was recovered. Do not count it as accepted or
   repeat an unknown-delivery request automatically. Any authorized replacement
   retains the original reservation and records possible duplicate billing.
5. Run one worker initially. Retry at most once only after a definite HTTP error
   or known-metered validation failure. Do not retry timeouts, unknown delivery,
   or charge-above-reservation. Stop on cap, route/privacy change or token-bound
   breach. Save new results atomically; do not resend valid completed batches.
6. Regenerate separate aggregate results and paired denominators. Original 980 and
   580 outputs remain unchanged. Report the route mix and follow-up date. Any
   later public aggregate update is a code/report deployment, not a production
   membership or golden import.

## Per-gap closure decisions for all 25 inventory rows

| Inventory rows / affected display | Concrete closure | Remaining evidence / approval |
|---|---|---|
|1–2 Summary verifier; readiness; Evals verifier |Publish matching sample metadata and 980/1,000 coverage now. Optional B supplies missing 20. |Publication A; B only if full planned sample is wanted. |
|3 Grouping Evals and Pipeline |Publish 580/600 coverage and valid-only agreement. Optional B supplies missing 20. |No production grouping replacement. |
|4 Extractor arm completion |Publish 100/82 attempt counts and 91/66 acceptance now. Optional D attempts the 18 untouched rows. |Existing failures stay in the original result; new continuation is dated separately. |
|5 Human evidence/entity quality |Keep structural quote checks distinct from relevance/correctness. |No human 20. New independent human judgments would be needed to claim this accuracy; not required for publication or model coverage. |
|6 Historical schema-error count |Keep the checkpoint cell unknown. |Only authentic attempt logs can close it; final outputs cannot imply zero. |
|7 Historical wall time |Use saved summed request time with its scope. |Invalid old wall timing cannot be repaired by a new timer. |
|8 Main-run cost |Publish known-charge scope and 46 unknown-charge calls. |Read-only billing reconciliation, then separately reviewed ledger changes. |
|9 Missing pre-run forecasts |Keep absent forecasts unknown. |A new forecast cannot become a historical pre-run forecast. |
|10–11 Cold/full-warm pilot |Publish saved cost/timing and fresh six-stage replay; build gate now passed. |No new inference or DB import. |
|12 Jev batching effect |Publish observed token difference and 64/100 joint agreement. |A controlled paired repeat would isolate variation; optional new study, no proposal to rerun main labels. |
|13 Planted tests |Publish 40/41 and 46/46 paired joins with missing counts. B repairs blind prediction gaps; C repairs seven planted and three unchanged auditor gaps. |Changed model claims remain unvalidated by humans even with complete coverage. |
|14 Injection |Publish zero 24 paired changes, bounded attack scope and benign-row contamination. |Broader attacks are a new optional study; no universal resistance claim. |
|15 Separate-run costs |Publish known charge,125 unknown-charge attempts and held exposure. |Provider receipts may reconcile billing; they do not create missing predictions. |
|16 Separate-run recovery |Publish phase arithmetic and zero resends of initially settled requests. |Private historical snapshots remain a separate evidence check; this does not restore main-run checkpoints. |
|17 Original 50 golden |Keep complete 26/38/30/14 scores, MAE 0.56 and existing limitations. |No new labels/rescore/import required. Human 20 remains declined. |
|18 Memo decision and business effects |Keep provisional ranking,164 checked claims and correct manual-assistant attribution. |Revenue/churn/causal impact needs product outcome data; no model call can supply it. |
|19 Historical memo-import field |Keep old manifest and use current memo checks. |No production manifest edit/import. |
|20 Main-run history and checker |Retain historical gaps and `review_required`. |Only authentic old artifacts or a genuine contract clarification can resolve their respective issues. |
|21 Method cache count |Publish 110,000 selection /83,003 distinct nonempty texts. |Code deployment only. |
|22 Option calibration |Keep unmeasured. |Original probability vectors were not saved; cannot reconstruct them from confidence. |
|23 Review-flag quality |Keep prompt-change counts distinct from flag precision/recall. |Independent human review decisions would be needed for accuracy; not authorized. |
|24 Pending/quarantine states |Preserve 6,522 pending,1,457 unresolved,1,791 quarantined and 1 empty. |Accepted 100,229 target is already met. Extra corpus processing is unnecessary for this release. |
|25 Integrity-check wording |Publish “saved import checks and current checks.” |No DB mutation. |

## What the original 17 files change

| File | Change |
|---|---|
|`dashboard/evals.json`|Generated 11-card registry: measured coverage, cost scope, pilot/warm and separate-run operations; internal source/config matcher. |
|`dashboard/server.py`|Attach verified sample counts only to matching source/config; keep population accuracy unknown; omit internal matching metadata from public Evals. |
|`docs/tasks.md`|Owner, scope, evidence, checks and publication boundary. |
|`reports/production-measurement-audit-2026-10-15.json`|Recomputed text-free coverage, paired joins, call/reservation arithmetic and source hashes. |
|`reports/production-measurement-audit-2026-10-15.md`|25-row gap inventory and evidence/approval distinctions. |
|`reports/production-measurement-warm-2026-10-15.json`|New real six-stage warm timing and before/after hashes; zero-call counters. |
|`tests/test_dashboard_evals.py`|New card coverage and public/internal metadata boundary. |
|`tests/test_measurement_audit.py`|Missing-output, hash/scope, malformed-evidence, warm-audit and cost regression checks. |
|`tools/build_eval_registry.py`|Build all cards from fingerprinted saved sources; retain unknowns; correct denominators and claims. |
|`tools/build_measurement_audit.py`|Offline recomputation from allowlisted public columns; no raw reviews or human answers. |
|`web/src/components/dashboard/evals-section.tsx`|Explain Partial status and import/current-check scope. |
|`web/src/components/dashboard/pipeline-diagram.tsx`|Show 600 selected /580 valid /20 missing grouping outputs. |
|`web/src/components/dashboard/readiness.tsx`|Show matched sample counts; never upgrade a sample to complete verification. |
|`web/src/lib/api.ts`|Type sample metadata and display small measured times in milliseconds. |
|`web/src/lib/measurement.ts`|Reject missing/inconsistent sample metadata and return only sample/pending. |
|`web/src/pages/index.astro`|Correct frozen-selection cache count and per-ID provenance wording. |
|`web/tests/measurement.test.ts`|Test sample-only readiness, invalid evidence and nonzero tiny time formatting. |

This follow-up adds only this closure plan and the aggregate preflight evidence,
and updates the audit/task notes to record the completed frontend gate. It adds
no package, runtime provider change, paid execution command or production import.
