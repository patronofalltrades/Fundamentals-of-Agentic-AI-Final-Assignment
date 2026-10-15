# Production measurement audit — 15 October 2026 UTC

## Result and scope

The production dashboard has saved measurements that were not connected to its
readiness display. It also has real missing outputs and historical evidence gaps.
Changing a badge cannot complete those measurements.

Audited [the live dashboard](https://hanif-spotify-insights.vercel.app/),
[summary API](https://hanif-spotify-insights.vercel.app/api/summary),
[evaluation API](https://hanif-spotify-insights.vercel.app/api/evals), and
[full memo](https://hanif-spotify-insights.vercel.app/memo/).
The browser was local Chrome on Hanif's connected Mac. The in-app browser was
blocked; no other computer was substituted. DOM reads were scoped to aggregate
sections. Review excerpts, human answer rows and private identifiers were not
returned to the model.

Base: merged PR34, `65d13968f7f2e7ff0c6b56cc3329512bea42339b`.
Local branch: `feat/production-measurement-audit`.
These fixes are **local only**. No model inference, production database write,
push, merge, deploy, upload or submission occurred in this audit.

## Highest-impact findings

1. `/api/summary.quality.blind_verifier` is hard-coded to `pending`, despite
   saved valid predictions for 980 of 1,000 selected reviews. The local fix
   matches both source hash and label configuration before attaching this
   sample. Population classifier accuracy remains unknown.
2. The 100-review cold/full-warm pilot is absent from Evals. A fresh free replay
   executed all six stages. It made zero paid, transport and socket attempts.
   The original database and copied rows, outputs and calls stayed unchanged.
3. Verifier and grouping cards say `Measured` although 20 outputs are missing
   in each sample. The local cards show valid/planned counts and `Partial`.
4. “Measured API cost, all stages” is only the known main-run labels/evidence
   charge. It excludes unknown charges and other project work. The local label
   now states that scope and shows 46 main-run calls with unknown charge.
5. Planted-test blind comparisons counted absent predictions in the denominator.
   The recomputed paired results are 40/41 changed-label disagreements, with
   two predictions missing, and 46/46 changed-issue disagreements, with four
   predictions missing. Changed model claims are not human-validated errors.

## Inventory and closure plan

`Display` means existing saved evidence can correct the presentation.
`Missing` means new evidence is needed. `Historical` means an authentic old
record must be found; a new run cannot recreate the old event.

| Page / field | Verified state and source | Kind | Closure / local action |
|---|---|---|---|
| Summary `quality.blind_verifier`; Issues → readiness | API says pending. Saved sample: 980/1,000 valid, joint agreement 648/980. [Recomputed aggregate](production-measurement-audit-2026-10-15.json). | Display + missing 20 outputs | Local API attaches matching aggregate only. UI stays sample-only. Finishing missing outputs requires a separately approved bounded run after holds are reconciled. |
| Evals → blind verifier | Topic 793/980, intent 901/980, severity 837/980, joint 648/980. 970 DeepInfra and 10 Crusoe valid outputs, per saved report. [Saved experiment](gap-closure-2026-10-16/aggregate.json). | Measured agreement; incomplete coverage | Show 980 valid / 1,000 selected and 20 missing. Separate prompt/blind input does not make model agreement human accuracy. Public call rows omit route fields. |
| Evals → recorded grouping; Pipeline | 580/600 valid, 449 exact matches, 503 family matches, 3 abstentions. Historical map is the comparator. [Saved experiment](gap-closure-2026-10-16/aggregate.json). | Missing 20 outputs | Show actual coverage. Remove claim that every charge is known. Additional attempts require explicit approval and preserved reservations. |
| Evals → extractor | DeepInfra attempted 100, accepted 91; Groq attempted 82, accepted 66. 18 Groq rows untouched. Known charge $0.006082951. [Extractor aggregate](extractor-benchmark-aggregate.json). | Real incomplete experiment | Correct “sent to each route” wording. Keep Partial. Completing the 18 untouched cases requires new paid calls; retrying 25 invalid cases is a separate scope. No guarantee of valid output. |
| Extractor evidence/entity quality | Exact quote validation is structural. Saved paired comparisons concern 63 overlapping accepted outputs, against development evidence. [Benchmark](openrouter-extractor-benchmark.md). | Human semantic quality missing | Do not equate exact quotation or model/development agreement with human correctness. Human20 was declined; no new human scoring was requested or generated. |
| Evals → labelling runs, checkpoint schema errors | Checkpoint JSON omits historical schema/identity-error count; final valid outputs cannot establish zero failed attempts. [Checkpoint](jev-checkpoint-500.json). | Historical | Keep unknown cell and label Partial. Recover genuine attempt records if available; do not derive zero from 500 final outputs. |
| Evals → prompt v1/v2 timing | Saved v2 wall duration is invalid across processes. Request sums exist. [Rubric report](jev-rubric-v1-v2-100.json). | Historical | Keep request time distinct from elapsed wall time. New benchmark timings must be a new experiment. |
| Evals → main-run cost | Known labels $3.264536184 + evidence $1.461436182 = $4.725972366; 46 uncertain calls. [Run aggregate](run-110k-calls-aggregate.json). | Scope/display + unknown billing | Rename as known main-run charge. Do not call this total project spend. Reconcile unknown charges only from authentic provider records. |
| Evals → estimate comparison | Pre-run estimate covers labels for the first 100,000 rows; actual selection is 110,000. Evidence cost and call-count forecasts were not saved. [Checkpoint](jev-checkpoint-500.json). | Historical forecast gap | Keep missing estimates unknown. A forecast written now cannot become a pre-run forecast. |
| Evals → missing cold/full-warm card | Separate 100-review pilot: 98 accepted, 2 quarantined, 112 calls, charge $0.007410287. Cold active 588.434599542 s; elapsed 1581.190059 s includes 992.755459458 s downtime. [Pilot](../cost/pilot/report.json). | Display, closed locally | Add saved cost and distinct time scopes. Pilot is separate from the main run. |
| New full-warm repeat | Six stages, orchestration 0.030836958 s; whole audit 1.316721 s. Zero paid/transport/socket attempts. [Fresh audit](production-measurement-warm-2026-10-15.json). | New free measurement, complete | Add card and millisecond formatting. Cached model outputs reused; rank recomputed. Original 98 accepted / 2 quarantines retained. |
| Evals → ten-review Jev batch | 100/100 outputs, joint agreement 64/100 with one-review main labels. Input average 852.7 versus 1015.7 in main run. [Saved experiment](gap-closure-2026-10-16/aggregate.json). | Measured comparison; causal effect missing | Replace “batching saved 16%” with observed sample difference. No paired single-review repeat was measured to isolate batching from ordinary variation. |
| Evals → planted labels/issues | Auditor flags: 40/43 changed-label cases, 48/50 changed-issue cases. Seven selected label plants lack auditor output. Blind joins also miss two/four outputs. [Recomputed aggregate](production-measurement-audit-2026-10-15.json). | Missing outputs + denominator/display bug | Use paired denominators and count missing outputs separately. Preserve old reports. Refrain from calling model perturbations proven human errors. |
| Evals → injection headline | Eight synthetic attack pairs; zero of 24 paired label/issue comparisons changed; 16/16 exact quotes; no canary leaks. In a mixed-batch probe, verifier and grouping each changed 1/8 benign rows, neither to attacker value. [Saved experiment](gap-closure-2026-10-16/aggregate.json). | Narrow measured probe | Replace general target-success headline with paired output changes. Target helper did not cover every format/ID/canary attack. No general security claim. |
| New separate-run operations card | 337 attempts, 213 logical requests; 212 settled, one without settled result. Known $0.040251779; held $0.373186624; exposure $0.413438403. 125 attempts have unknown charge. [Recomputed aggregate](production-measurement-audit-2026-10-15.json). | Display + real billing gap | Add Partial card. Holds include 112 HTTP429, 12 HTTPError and one unusable-response attempt. Errors are not assumed free. |
| Separate-run interruption/resume | 15 initial, 322 resumed attempts; three initially settled logical requests were not resent. Saved report describes SIGINT/checkpoints. | Measured log arithmetic; private checkpoint provenance not rechecked here | Preserve distinction between public call arithmetic and saved-report assertions. This does not replace the historical main-run checkpoint pair. |
| Human golden evaluation | Original50 complete: topic26/50, intent38/50, severity30/50, joint14/50; severity MAE0.56. Alternate intent-only runs are a different evaluation configuration. | Complete diagnostic; population validity limited | No rescore or answer exposure. Retain overlap/contamination and single-labeller limits. “9” is a separate selected-production diagnostic, not this completed50 evaluation. |
| Memo → provisional / confidence / revenue | Live memo has164 checked claims. Manual assistant16/40 comparison is not production grouping accuracy. Human corrections are no longer holdouts. Reviews contain no revenue/churn/causal outcomes. | Genuine decision/measurement limit | Preserve provisional ranking and attribution. Model calls cannot measure business impact. A real product study or authorized human validation would be separate work. |
| Summary import metadata `memo_claim_check: missing` | Old import-time manifest says missing; current memo API is `claims_checked_provisional`. | Historical snapshot, not current missing claim check | Preserve manifest. Use current analysis/memo checks for current state; no production DB rewrite. |
| Pipeline history / grading `review_required` | Main-run historical role usage/provenance/checkpoint gaps remain. Checker also expects660,622 source rows versus110,000 selected. | Historical + contract-scope difference | Keep unchanged checker and scope disclosure. New experiments do not manufacture old receipts/checkpoints. No new scope approval was requested. |
| Method cache count | Live prose says100,000/75,894; live summary says110,000 selected/83,003 distinct nonempty texts. | Stale display, closed locally | Use frozen selection counts and per-ID provenance wording. |
| Method → option calibration | Original option probability vectors were not saved; confidence is not a substitute. | Historical | Existing confidence cannot recreate full option probabilities. A new paid/calibration study would be separate. |
| Prompt benchmark → review flags | The prompt comparison reports how often `needs_review` changed. It does not score the flag's precision or recall against human review decisions. [Rubric report](jev-rubric-v1-v2-100.json). | Quality unmeasured | Keep flag frequency distinct from flag correctness. No human review decisions or routing thresholds were generated in this audit. |
| Row states → pending/unresolved/quarantined | Accepted100,229; pending6,522; unresolved1,457; quarantined1,791; empty1. These sum to110,000. | Genuine processing states | Accepted target is met. Preserve all selected IDs and reasons. Processing more reviews requires new authorization; states are not display defects. |
| Integrity checks | Import recomputed ranking; API checks current memo claims and database text boundary. | Wording scope | Replace “run every request” for all checks with “saved import checks and current checks.” |

## New measurement method

`tools/build_measurement_audit.py` reads only already-public, text-free case
CSVs, call JSONL and aggregate reports. It enforces case-column allowlists,
distinct hashed references and call-field allowlists. It recomputes paired joins,
coverage, model agreement, phase counts, settled logical requests and known/held
costs. It checks those costs and verifier counts against the saved aggregate.
Only aggregate counts and source-file hashes are written. No case references,
review text or human answers enter the new report.

The new warm audit used the existing `tools.audit_cost100_full_warm` harness.
It copied the real private pilot, checked pinned source bytes, blocked paid
entry points, provider transport and sockets, and compared before/after hashes.
The new report contains aggregates only. Private source/database copies remain
outside Git with restrictive permissions. It is a new warm experiment, not a
fabricated historical cold phase or checkpoint.

## Remaining approvals and blockers

- **Publish these local code/report changes:** requires new explicit authorization
  for a GitHub branch/PR and subsequent merge/Vercel deployment. Destination is
  this repository and its existing website. Payload is code and aggregate-only
  reports; no reviews, answers or private DBs. No inference cost. Provider hosting
  billing is not changed or asserted free. PR34 approval does not cover this work.
- **Finish missing model outputs:** not approved. First reconcile held attempts,
  verify current route prices/access/privacy limits and present a bounded plan.
  Potential data would be only the frozen experiment's source texts and required
  IDs, sent through the originally approved providers/routes; no human answers.
  Exact routes, token limits, retry count and spend ceiling must be specified
  before any request. Historical $0.00086 for18Groq is not a current quote.
- **Resolve billing unknowns:** authentic provider receipts or an authorized
  read-only billing export are needed. Do not release reservations from HTTP
  status alone, top up accounts, or change credentials.
- **Recover history:** only genuine old logs/receipts/checkpoints can close those
  gaps. If unavailable, disclose them. A new run can measure future behavior only.
- **Human/product quality:** no new human20 is authorized. Human answers cannot
  be generated. Business impact requires real outcome evidence.
- **Frontend production build:** this isolated worktree has no `node_modules`.
  No dependency install is authorized. Pure TypeScript tests run with installed
  Node; an Astro build remains a release check in a dependency-ready environment.

## Checks and handoff

Final validation: 430 Python tests ran; 428 passed and two skipped because this
isolated worktree has no private golden-gap plan. Four Node tests passed.
The CLI help command, both generated-report checks, `git diff --check` and all
relative links in this inventory passed. The fresh warm replay passed with no
new calls. Its private directory is mode0700; none of its files permits group or
other access. The exact local commit/file list is in the completion handoff.

The first complete suite caught an unintended internal
source/config object in `/api/evals`; the route now removes that internal object.
The existing privacy assertion was preserved. Summary exposes validated counts
only. Targeted privacy/scope regressions passed after the fix.

Historical reports, `cost/`, frozen datasets, checker code, human answer files,
private grading candidate and production DB are unchanged.
