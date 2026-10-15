# Course rubric assessment — 16 October 2026

**Refreshed 15 October 2026 UTC after PR #33.** GitHub reports
[PR #33](https://github.com/patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment/pull/33)
merged at **19:57:09 UTC**. Its head is
`9bee1bd35e03586fbdfa8c080fa770aa838c635c`; current verified main and the merge
commit are `53a9ce3a7eb2b5a51ab7a82f055603506a09669d`. The evidence below is
published on main, not merely on `feat/gap-closure`. This assessment refresh is
a separate local change on `docs/rubric-refresh-pr33`; it has not been pushed.

The filename retains Hanif's requested 16 October date. Status means
**Evidenced**, **Partly evidenced**, or **Not evidenced** for the stated
criterion, not a predicted grade. The original assessment began at `bc63e0d`;
the previous refresh covered PRs #30/#31. PR #32 published that closeout and
the historical implementation-note banner. This review supersedes their stale
publication and remaining-gap statements, while retaining their dated evidence.

**Audit boundary.** Read the report, both aggregate JSONs, all five public case
CSVs, `calls.jsonl`, both new tools, their tests, and registry integration.
Recomputed case counts, agreement, planted detection, costs, holds, and phase
arithmetic with separate standard-library code. No source review text, human
answer columns, private run database, or private checkpoint payload was opened.
No model-calling command, paid call, human20 evaluation, or grading-data edit ran.

## Rubric, scope, and deadline

D1–D4, T1–T3, and W1–W3 retain the criterion mapping from the prior audit of the
[assignment document](https://docs.google.com/document/d/1PUFw56OGxqbUxiFm0vKtsWX8ac8633BgOlCSGa3TgLA/edit).
The [11 October announcement](https://bcourses.berkeley.edu/courses/1555592/announcements/7376947)
and the prior direct document check support **20 October 2026, 23:59 Pacific**.
This pass does not revise that deadline or its README line.

Hanif confirmed acceptance of the 100k scope on 15 October. The 110,000 selected
and 100,229 accepted rows meet that minimum and his stricter accepted-row goal.
The unchanged full-corpus checker still uses 660,622 IDs and returns
`review_required`. Keep the accepted scope and that checker result distinct;
do not ask Hanif to reconfirm the same scope. The new human20 holdout is **not
being done, by Hanif's decision**. No action below requests it.

## Status decisions after PR #33

| Criterion | Previous → current | Reason for change or retention |
| --- | --- | --- |
| D1 | Evidenced → **Evidenced** | Code, methods, reports, case files and registry are published; setup and offline tests work. Private reproduction inputs remain disclosed. |
| D2 | Partly evidenced → **Partly evidenced** | The 600-case trail and a new recorded grouping stage close specific gaps. Historical usage, direct-origin coverage, main-run checkpoints, and public per-call route/receipt links remain incomplete. |
| D3 | Partly evidenced → **Partly evidenced** | Prior ranking/claim arithmetic stands. New agreement evidence does not establish semantic correctness or repair split source provenance. |
| D4 | Evidenced → **Evidenced** | PR #33 does not change the recommendation or its checked alternatives and limitations. The prior D4 assessment is preserved below. |
| T1 | Partly evidenced → **Partly evidenced** | The original 50 human comparisons remain; no new human reference or missing semantic/entity/review-flag evaluation was added. Human20 is declined. |
| T2 | Partly evidenced → **Evidenced** | Real blind-model, planted-perturbation and injection outcomes now have saved results and auditable counts. This credits the scoped testing, not human accuracy, model-family independence, or universal attack resistance. |
| T3 | Partly evidenced → **Partly evidenced** | New real interruption and usage evidence strengthen operations; US$0.373186624 remains held and historical usage/main-run recovery evidence is still missing. |
| W1 | Partly evidenced → **Partly evidenced** | Accepted minimum met; the main population and unchanged full-reference checker flags are unaffected. New sample tests do not complete pending source rows. |
| W2 | Partly evidenced → **Partly evidenced** | Runnable grouping, actual ten-review requests and new-run SIGINT/resume are demonstrated. They do not retrofit the one-review main Jev run or supply its missing checkpoint pair. |
| W3 | Evidenced → **Evidenced** | Ranking/database/backend evidence stands; the saved and live evaluation registry now expose the new results. Publication does not validate product priorities. |

## Verified additions and denominators

Sources: [run report](gap-closure-2026-10-16.md),
[run aggregate](gap-closure-2026-10-16/aggregate.json),
[call log](gap-closure-2026-10-16/calls.jsonl), and
[recovered trail](grouping-trail-recovery-2026-10-16/aggregate.json).
The following case arithmetic was independently recomputed from the public CSVs.

| Evidence | Planned / observed | Recomputed result and limit |
| --- | --- | --- |
| [Blind verifier cases](gap-closure-2026-10-16/verifier_cases.csv) | 1,000 selected; **980 unique scored rows** | Topic 793/980, intent 901/980, severity 837/980, joint 648/980; severity MAE 0.1714. Of 100 logical ten-review requests, 98 succeeded, one was metered/quarantined, and one remained held without usable output. Two batches (20 reviews) are excluded, including the missing held ten-review batch. |
| [Recorded grouping cases](gap-closure-2026-10-16/grouping_cases.csv) | 600 selected; **580 unique outputs** | 449/580 exact issues, 503/580 families, 3 abstentions; 449/577 among non-abstentions. Two ten-review requests were quarantined. These are comparisons with historical model assignments. |
| [Planted label cases](gap-closure-2026-10-16/planted_label_cases.csv) | 50 perturbed + 50 unchanged planned; **90 scored** | 40/43 scored perturbations flagged: 19/20 topic and 21/23 severity. 5/47 unchanged Jev labels flagged. Seven perturbed and three unchanged rows are missing after one rejected batch. Only 41/43 perturbed rows join to blind verifier outputs: 40 disagree, one agrees, two are missing. The reported blind 40/43 includes missing outputs in its denominator. |
| [Planted issue cases](gap-closure-2026-10-16/planted_issue_cases.csv) | 50 perturbed + 50 unchanged; **100 scored** | 48/50 perturbed issues flagged; 3/50 unchanged historical issues flagged. Only 46/50 perturbed cases join to grouping outputs; all 46 disagree and four are missing. The reported blind 46/50 includes missing outputs in its denominator. |
| [Recovered historical cases](grouping-trail-recovery-2026-10-16/verifier_600_cases.csv) | **600 unique cases** | 511/600 issue agreement; 323/327 when both marked high confidence. These figures reproduce the October 11 handoff. |

The Jev batching aggregate reports **100/100** outputs in **10 requests of 10**,
with joint agreement **64/100**, hence **36/100 changed** versus saved single-review
labels. All ten calls are metered successes; their input total is 85,267 and
charge is US$0.003581214. The per-case batched predictions are not in the public
CSV set, so 64/100 is an aggregate result whose method/tests were checked,
not a fresh public per-row recomputation. The reported 852.7 versus 1,015.7 input
tokens per review compares this sample with the main-run average; it is not a
paired causal estimate. Single-review repeat variability was not measured.
Original labels remain unchanged.

The eight synthetic injection pairs have **0/24 paired label/issue changes**
across Jev, verifier and grouping in the saved aggregate. Canary leaks are zero;
the evidence stage accepted 16/16 exact quotes. In the contamination batch,
one of eight benign rows changed in each of verifier and grouping, neither to
the recorded attacker value. This is a small test, not universal resistance.
The target-matching helper checks only topic/intent/severity/issue fields:
format, ID and canary attacks rely on separate schema/ID/leak checks. The
headline “0/24 target successes” is therefore not 24 identical target tests.
Actual response bodies and injection per-row outputs remain private; this pass
checked aggregate outcomes, successful call counts, implementation and tests.

## Deliverable quality

### D1 — Accessible code, setup, and artifacts

**Evidenced; unchanged.** The [README](../README.md) links the live site,
source, grading release, setup, calculator and assessments. PRs #30–#32 already
published the expanded memo, full warm audit, cost/provenance reconciliation,
and historical implementation banner. PR #33 adds runnable source, reports,
hashed case references and tests. The new registry matches its source reports.
The former local-only-publication gap is closed.

Reproduction of the private request/response run and historical input batches
still requires their private artifacts. The public case files support the
recomputations above; public availability is not a claim that every receipt or
checkpoint is exported. No dataset or human answer release is required here.

### D2 — Clear architecture, shared schema, and provenance

**Partly evidenced; unchanged, with substantial gaps closed.** Diagrams,
[contract](../spotify_pipeline/contract.py), queues and shared ledger separate
model roles from code-owned identity, hashing, accounting and state. The new
[evaluation tool](../tools/gap_closure_eval.py) constructs blind verifier inputs
from IDs/text/rubric; grouping sees labels/quote but not the historical issue.

The [recovery tool](../tools/recover_grouping_trail.py) links eight historical
chunks, **159 input batches / 30,403 outputs**, and the verifier's **three
200-row inputs / 600 outputs**. Published hashes, row-accounting booleans and
case arithmetic support the recovered trail. Input headers omit grouping
issue/confidence columns; the tool checks those fields and separate reference
sets. This closes “no supplied 600-case trail.” It does not independently prove
all unseen chat context or produce absent API usage receipts. The original
private input files were not reopened in this pass.

The new run records 337 attempts with roles, phases, usage and holds. A follow-up
fix added each attempt's `route` and request hash to the public `calls.jsonl`,
plus a response hash for the 324 with a saved body and a generation ID for 186. The historical main export still has 20,938
split/indirect-origin records, absent role receipts and no checkpoint pair.
Keep authentic separate origins; do not turn new-run evidence into old receipts.

### D3 — Memo numbers linked to calculations and source evidence

**Partly evidenced; unchanged.** The prior release audit recomputed all 41
severity sums, means/ranks and 164 claims. PR #33 changes no baseline ranking,
claim or memo artifact. Baseline `USE-ADS` remains 5,197 / severity sum 11,874;
the public projection is 5,195 / 11,869. The recovered 30,403 raw assignments,
30,400 corrected baseline members and 30,377 public members are distinct
stages, as the [grouping handoff](grouping-v4-handoff.md) explains.

The new case comparisons and recovered trail improve source-to-assignment
auditability, but neither side is a human semantic reference. They do not
establish representative-quote support, validate every issue membership, or
repair split call/cache provenance. This pass did not rerun the full release
ranking/checker or score human answers; it retains that dated arithmetic proof.

### D4 — Coherent recommendation, alternatives, and limitations

**Evidenced.** PR #30 published the [expanded decision memo](product-decision-memo-2026-10-13.md).
It prioritizes ads discovery, retains playback reliability as the competing
option, separates investigation from delivery, and states effort/value
hypotheses, a proposed outcome, guardrails, and stop conditions. Its top-five
public figures and totals were checked against the release. It preserves
historical, self-selected-data and semantic-accuracy limits and makes no
observed revenue/churn or causal claim.

The inclusion and alternative-analysis gap is closed. The recommendation
remains provisional; this criterion assesses the argument's coherence, not
whether the issue mapping has been validated. D2/D3/T1/T2 limits still apply.

## Testing and evaluation

### T1 — Fifty human labels, per-field comparisons, and error analysis

**Partly evidenced; unchanged.** The original [golden diagnostic](golden-gap-and-checker-2026-10-12.md)
has 50 completed predictions: topic 26/50, intent 38/50, severity 30/50, joint
14/50, severity MAE 0.56 and sentiment MAE 0.21. Confusion/error aggregates
exist. No answer columns were read or rescored here.

PR #33 adds model agreement and synthetic behavior tests, not human accuracy.
Semantic evidence-quote correctness, unsupported entities and `needs_review`
prediction quality remain incompletely measured. Twelve original human cases
ask for review; eight golden texts overlap development material and earlier
golden influence remains unresolved. The original diagnostic is retained with
these limits. **No human20 holdout is requested or credited, by Hanif's decision.**
Its earlier preparation or entity-assistance work does not establish an
independent human-reference evaluation.

### T2 — Independent verification, planted-error, and injection outcomes

**Evidenced; upgraded from Partly evidenced.** The missing real behavioral
outcomes now exist: 980 blind labels, 580 grouping outputs, scored planted
perturbations, eight injection pairs and contamination checks. Public case
files reproduce the numeric results, and the historical 511/600 trail is now
supplied. Synthetic transport tests supplement these recorded outcomes; they
are not being substituted for the paid run.

The upgrade credits test design, saved outcomes and disclosed failures.
Verifier/auditor/grouping use **`openai/gpt-oss-120b`, the extractor's base model**,
with separate instructions. The verifier is blind to Jev's first prediction,
but this is not independence from every pipeline model or a human reference.
The aggregate splits 970 verifier labels on `deepinfra/bf16` and **10 on
`crusoe/bf16`** (joint agreement 643/970 and 5/10). Token/charge arithmetic
supports 97 and one successful ten-row calls at those respective prices;
the public log now records each call's route, and its generation IDs can be checked with the provider.

Perturbed values are known changes to model outputs, not newly human-validated
truth. Flags on unchanged values are disagreements, not calibrated false
positives. Missing batches, model dependence, limited injection applicability
and the scope distinctions above stay attached to these results. The earlier
assistant-manual 16/40 exact and 21/40 family comparison is still not
production-model accuracy. The older agent audit has a separate 16/40 exact
and 22/40 family result. Their [artifact attribution](grouping-score-provenance-2026-10-15.md)
is reconciled; a blind provider-execution trail is not reconstructed.

### T3 — Real cold/warm pilot, offline calculator, and operational controls

**Partly evidenced; unchanged.** The published cold pilot remains 100 inputs,
112 metered calls, 98 completed / two quarantined and US$0.007410287; active
time is 588.4346 seconds. The [offline calculator](../cost/README.md) uses
saved usage and editable rates; its earlier sensitivity check remains dated
evidence. The [full warm audit](cost100-full-warm-audit.md)
exercises all six stages on a copy with unchanged outputs/calls and zero new
transport attempts. It is distinct from the 0.008029-second validation path.
Full warm repetition still needs the private pilot database.

PR #33 adds real-run phases, metered rejection handling and reported SIGINT/
resume evidence. The public call log independently sums to **US$0.040251779
charged + US$0.373186624 held = US$0.413438403 exposure**, below this separate
run's reported US$1.50 cap. This is not the superseded human20 US$0.12 proposal.
All 212 metered calls have usage and charges within their reservations.
There are **112 HTTP429 attempts**, 12 older HTTP errors without a recorded
status code, and one unusable-response hold. The 125 null charges stay unknown.
Historical grouping/verifier usage and complete project billing remain unknown;
account reconciliation and the main-run checkpoint gap prevent an upgrade.
Summed request durations are not elapsed wall time.

## Working result

### W1 — Ingestion, coverage, and successful classification

**Partly evidenced; unchanged.** The accepted scope is met: 110,000 selected
IDs, 100,229 structurally completed, 1,791 quarantined, 1,457 unresolved,
6,522 pending and one empty. PR #33 samples saved results; it does not complete
the remaining source rows or enlarge the main run. The saved full input is
660,622 IDs, with 660,609 nonempty texts and 13 empty texts.

The [unchanged full-reference checker](grading-closeout-2026-10-15.md) still
reports 550,622 missing IDs and `review_required`. Hanif's confirmed 100k scope
does not make that checker pass. Retain both the met minimum and the explicit
full-corpus diagnostic flags. No new corpus profiling or checker execution ran.

### W2 — Runnable bounded stages, saved handoffs, and demonstrated resume

**Partly evidenced; unchanged, with new mechanisms demonstrated.** The pilot
harness already separated label/evidence/verify/group/rank/memo. PR #33 now
supplies a recorded program grouping stage, actual ten-review verifier and Jev
requests, durable attempt keys, shared reservations, bounded retries and
quarantine checks. The new grouping-stage implementation gap is closed.

The aggregate records a real SIGINT, exit 130 and checkpoints at
`2026-10-15T17:40:00.091134+00:00` and `2026-10-15T19:26:17.582261+00:00`.
The call log reproduces **15 initial / 322 resumed attempts**, three initially
settled calls, and **zero resumed attempts for those settled logical requests**.
Final state is 208 successes + four metered quarantines = 212 settled logical
requests, with one logical request still held. The 125 held attempts include
failed earlier attempts; they are not 125 missing logical requests. Private
checkpoint payloads were not independently reread here.

These close the “only synthetic recovery” gap for the new run. They cannot
reconstruct the main-run checkpoint pair. **All 76,523 historical Jev requests
still contain one review.** The new 100-review test demonstrates ten/request
but changes 36 labels, so it does not replace or retroactively comply for the
main run. Original evidence batches and accepted counts remain unchanged.

### W3 — Reproducible ranking and usable database-backed deployment

**Evidenced; unchanged.** The prior release audit reproduces `severity_sum`
descending and issue-ID tie-breaking, and the published Python backend serves
stored results to the dashboard. PR #33 adds aggregate evaluation cards without
rerunning the business pipeline. Both `/api/summary` and `/api/evals` returned
HTTP 200 in this audit. The live summary reports 100,229 accepted rows, and
all nine live evaluation items and their source hashes match the saved registry.
The registry is current against its saved sources. Existing ranking, database
and memo evidence remains intact.

The 600-case historical agreement and new 980/580 comparisons describe model
agreement, not validated product priorities. Keep baseline/public denominators
and provisional recommendation labels visible. No new deployment was triggered.

## Remaining evidence conflicts

1. **Public call provenance is narrower than the prose.** The gap report says
   `calls.jsonl` includes routes; its 13 exported columns do not. The tool stores
   route in SQLite but drops it from the published projection. Request/response
   hashes, provider IDs, the reported provider-cost equality and raw checkpoint
   contents also cannot be directly audited from this export. The aggregate's
   970/10 split is consistent with token/rate arithmetic, not a replacement for
   those receipt fields. No evidence file was edited to hide this difference.
2. **Planned, scored and joined denominators differ.** Verifier 1,000/980;
   grouping 600/580; planted label audit 50/43. A held ten-review verifier batch
   and a separate metered/quarantined ten-review batch explain its 20 excluded
   rows. Blind planted comparisons report 40/43 labels and 46/50 issues, but only
   41 and 46 rows respectively have blind outputs. Observed disagreement is
   40/41 and 46/46; the two and four missing outputs are neither agreement nor
   successful detection. “0/24 targets” mixes semantic target checks with
   separate schema/ID/canary checks. The Jev 64/100 comparison and injection
   details lack public per-row output.
3. **Holds are not charges or zeroes.** The log sums to US$0.040251779 known
   charges (Jev US$0.004269636; OpenRouter US$0.035982143) and US$0.373186624 held.
   Holds comprise US$0.305261716 for 112 HTTP429 attempts, US$0.066551808 for 12
   older HTTP errors, and US$0.001373100 for one unusable response. Provider
   balance/receipt reconciliation remains open; this audit did not clear holds.
4. **Recovered history is not a complete bill or main-run replay.** The 600-case
   trail and 30,403 raw assignments are supplied. Historical API usage, direct
   call origins and the main-run checkpoint pair are still absent. The unchanged
   checker retains 7,980 nonaccepted statuses, 949 nonbinary outcomes, 79,797
   unknown phases, 94 missing usage fields (47 calls), 20,938 split/indirect
   origins, missing roles and full-corpus scope flags. PR #33 does not rewrite
   the grading ZIP or its US$4.725972366 main-run metered total.
5. **Human-reference limits remain.** Model agreement, changed model labels and
   synthetic attacks do not establish human semantic accuracy. The golden-50
   overlap/influence limits and assistant-manual 40-case attribution remain.
   Human20 is declined; do not list it as an outstanding action or count
   AI-assisted entity entries as independent human gold.
6. **Stale coordination wording remains outside this edit scope.** The gap report
   still calls deadline and minimum scope instructor questions. This assessment
   uses the supported October 20 deadline and Hanif's accepted 100k scope while
   preserving checker flags. Other reports and cost/dashboard files are untouched.

## Checks for this refresh

- GitHub PR state, head, merge time and main SHA verified; isolated worktree is
  based on the published merge. No branch-only execution evidence is substituted.
- `python3 -m unittest discover -s tests -t . -q`: **422 tests, OK, 2 skipped**.
  The private golden-plan tests skip in this clean checkout.
  Model interactions inside tests use synthetic fake transports. A sandbox
  rerun hit the localhost socket restriction; the permitted rerun passed in
  14.581 seconds.
- `python3 -m spotify_pipeline --help`: passed.
- `python3 tools/build_eval_registry.py --check`: passed; no file written.
- Independent CSV/log arithmetic reproduced the counts, exact agreement,
  severity MAE, planted flags, 511/600 and 323/327, 337 unique attempt keys,
  213 logical requests, phase counts, known charges and full held exposure.
- Read source for `gap_closure_eval.py`, `recover_grouping_trail.py` and their
  tests; did not execute either command-line tool or open private payloads.
- The old D4 section and README October 20 deadline line are preserved byte for
  byte. Only this assessment and the README assessment pointer are in scope.
- Original release arithmetic and checker results are retained as dated prior
  evidence; neither was rerun or represented as a new pass.

## Prioritized actions through 20 October — after PR #33

These are review actions, not authorization for paid calls, publication,
deployment, new human labeling or submission. No human20 work is requested.

| Priority | Action | Criterion / acceptance check | Owner |
| --- | --- | --- | --- |
| 1 | Reconcile the 125 held attempts using authentic provider/account evidence. | T3: retain US$0.373186624 until an evidence-backed disposition exists; unknown cost is never zero. No retry or new inference is implied. | Execution/billing owner |
| 2 | Review the public provenance mismatch and exact failed-batch denominators. | D2/T2/W2: provide an approved text-free route/receipt/checkpoint addendum, or correct the broader prose; distinguish selected/scored/joined denominators, missing blind outputs and the limited 0/24 test. Requires separate file-scope handoff. | Original execution owner + reviewer |
| 3 | Retain historical limits and the original production labels. | D2/T3/W1/W2: recovered 511/600 trail is credited; no invented usage/phases/checkpoints, no ten-review retrofit, no replacement of labels from the 36/100 shift. | Coordinating reviewer |
| 4 | Review and publish only the approved documentation change. | D1: this local two-file assessment commit, unchanged deadline and D4, passing offline checks, explicit human20 decision. Publication requires approval; this task does not push. | Hanif + reviewer |
| 5 | Recheck final accessible evidence links and live read-only routes before submission. | D1/D3/W3: retained release checksum, current evaluation registry, separate main/new-run cost scopes, provisional memo and unchanged checker flags. | Final reviewer |
| 6 | Submit the approved repository URL by 20 October, 23:59 Pacific. | Save the course receipt. Submission remains Hanif's action; this review does not submit. | Hanif |
