# Course rubric assessment — 16 October 2026

**Evidence checked on 15 October 2026 UTC.** The report date and filename follow
Hanif's request. This is an evidence assessment, not a predicted grade or point
total. Status means **Evidenced**, **Partly evidenced**, or **Not evidenced** for
the stated criterion. A working component does not establish every related claim.

**Scope and owner.** Codex prepared this report on
`docs/rubric-assessment-2026-10-16`, from main
`bc63e0d6b9b7744ba40834e30ef8401cea86570b`. The edit scope is this report and
the two assessment pointers. The existing `feat/decision-memo-diagrams` work
stays in its separate checkout. No paid inference, new extraction, human label
collection, or golden scoring was performed. Human answer columns were not read.

## Rubric and deadline

The authoritative [assignment Google Doc](https://docs.google.com/document/d/1PUFw56OGxqbUxiFm0vKtsWX8ac8633BgOlCSGa3TgLA/edit)
was read directly. The D1–D4, T1–T3, and W1–W3 identifiers below map, in order,
to its four deliverable criteria, three testing criteria, and three working
result criteria. They do not substitute the older benchmark's A–M requirements.
The Doc says that evidence quality matters and that low label agreement alone
does not prevent a sound evaluation.

**Planning deadline:** 21 October 2026 at 23:59 Pacific, as Hanif instructed and
current [AGENTS.md](../AGENTS.md) records. The Google Doc currently says
**20 October at 23:59 Pacific**. Confirm the extension with the instructor.
Prepare a submission-ready package by the earlier date while this is unresolved.

## What is published and verified

- [PR #27](https://github.com/patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment/pull/27)
  and [PR #28](https://github.com/patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment/pull/28)
  are merged. Current main is `bc63e0d`.
- The public [dashboard](https://hanif-spotify-insights.vercel.app/) and
  [memo](https://hanif-spotify-insights.vercel.app/memo/) load. The memo filter
  changes 41 issues to one issue and four claims for `USE-ADS`. Its saved values
  are 5,197 complaints and severity sum 11,874. Verify is implemented as a
  **sample-only** state, with the 600-case limitation. Chrome confirmed the
  rendered label and explanation; see [readiness.tsx](../web/src/components/dashboard/readiness.tsx).
- The live Pipeline section shows extraction, code/model boundaries, the
  historical grouping/verifier handoff, database, backend, dashboard, and isolated
  evaluation. Both published [extraction](../docs/pipeline-extraction.mmd) and
  [analysis](../docs/pipeline-analysis.mmd) sources are byte-identical to the
  preserved local originals. Their SHA-256 hashes are respectively
  `d2a85f8c2f018e246942b42cc41dbb2ed3166d64b78e84ad3b2b934802de0321`
  and `ae809e9dec036a59296bea606a0b99ff7cdabdc21e88ac9335936af2c9fd912e`.
- The published [flow API](https://hanif-spotify-insights.vercel.app/api/flow)
  contains 30,377 records, 16 nodes, and 60 links. Every link and node count
  matches the preserved `complaint-flow.json` after one explicit display-node
  alias: local `issue:OTHER36` becomes API `issue:OTHER`. Link order and JSON
  metadata also differ. This is count-for-count agreement, not identical JSON.
  The live Sankey and diagrams are **published**; the local aggregate JSON and
  its generator are separate artifacts.
- [Release `grading-2026-10-13`](https://github.com/patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment/releases/tag/grading-2026-10-13)
  contains `grading-110k.zip`, `SHA256SUMS.txt`, and the synthetic resume video.
  The ZIP downloaded without account credentials. Its SHA-256 matches GitHub:
  `a596dae7c47c61b864e03e374e6165b443222fc736e0c741c6e03d5db68d9198`.
  It contains 110,000 distinct source IDs, 100,229 completed records, 30,400
  distinct memberships, 41 ranking rows, 164 claims, and 79,797 call records.
  It contains no main-run checkpoint pair.

## Deliverable quality

### D1 — Accessible code, setup, and artifacts

**Evidenced.** The [README](../README.md) links the public site, source,
grading release, setup, tests, and offline calculator. The release ZIP was
downloaded and checked. The [cost directory](../cost/README.md) contains dated
rates, pilot records/calls, reports, and checkpoints.

**Gap:** Some historical architecture/implementation prose still describes an
unrun foundation. Local additions listed below are not delivered artifacts.
Resolve those entry-point inconsistencies before submission.

### D2 — Clear architecture, shared schema, and provenance

**Partly evidenced.** The published diagrams now describe actual stages and
their boundaries. [Contract code](../spotify_pipeline/contract.py),
[queue code](../spotify_pipeline/checkpoint5000_queue.py), and the
[shared ledger](../spotify_pipeline/project_budget.py) own identities, hashing,
state, reservations, and validation. The release saves labels, configuration,
membership, and call metadata.

**Gap:** The large grouping run was a historical agent handoff. Its per-call
verifier/group/memo records and main checkpoints are missing. The saved checker
reports 20,938 completed records with split or indirect provenance that cannot
be represented as one direct origin. Keep both authentic origins; a clearer
diagram does not fill missing records. See the
[provenance reconciliation](prepublication-reconciliation-2026-10-12.md).

### D3 — Memo numbers linked to calculations and source evidence

**Partly evidenced.** This audit independently joined release membership to
completed complaint/cancellation records, recomputed all 41 severity sums,
six-decimal half-up means, and deterministic ranks, and checked all 164 claims.
All matched. The [live claims](https://hanif-spotify-insights.vercel.app/api/claims)
match the release. The [memo](provisional-product-priority-memo.md) cites claim
IDs. Baseline ads counts are 5,197 / 11,874; the public projection is 5,195 /
11,869 because it excludes known flags.

**Gap:** Arithmetic and exact quote membership do not prove semantic support.
The incomplete verifier trail and split provenance still limit the full
source-to-claim audit. Review material claims and representative source support
without claiming human-validated issue membership.

### D4 — Coherent recommendation, alternatives, and limitations

**Partly evidenced.** The published provisional memo puts the ads finding first,
compares it with more severe playback complaints, and recommends targeted human
review before product change. It states the historical, self-selected data
limits and avoids revenue, observed churn, and causal claims.

**Gap:** The published memo has little discussion of competing actions, effort,
tradeoffs, success measures, and stop conditions. The fuller decision memo is
still local. Decide whether to include it after reviewing its claims and limits.

## Testing and evaluation

### T1 — Fifty human labels, per-field comparisons, and error analysis

**Partly evidenced.** Published [golden evaluation documentation](golden-gap-and-checker-2026-10-12.md),
the [live summary](https://hanif-spotify-insights.vercel.app/api/summary), and
existing private aggregate reports agree: all 50 predictions are complete;
topic 26/50, intent 38/50, severity 30/50, joint 14/50; severity MAE 0.56 and
sentiment MAE 0.21. The saved aggregates include confusion and error counts.
This audit read aggregate results only and did not rescore answers.

**Gap:** Evidence-quote semantic accuracy, unsupported entities, and prediction
quality for `needs_review` are not fully evaluated. Twelve human cases ask for
review. Eight texts overlap development material, and earlier golden influence
is unresolved. Keep the original 50 and these limits. A fresh holdout is needed
for a new accuracy claim after answer-influenced changes. The local human20
packet is not a completed or published evaluation in this assessment.

### T2 — Independent verification, planted-error, and injection outcomes

**Partly evidenced.** The [cost harness](../tools/cost100_harness.py) has a blind
source-and-rubric verifier. The historical grouping handoff reports 511/600
model agreement, and the UI labels its limited scope. Published
[synthetic boundary tests](free-verification-boundaries-2026-10-12.md) cover
identity, exact spans, changed labels, and public output boundaries.

**Gap:** The complete 600-case blind-input/prediction trail is not supplied.
Synthetic mock checks do not establish that a model detected planted semantic
errors or resisted review-text instructions. Also, the reported 16/40 comparison
was an assistant's manual assignment against human answers, with aggregate
family counts seen before freezing; it was not a fresh production-model accuracy
test. See [its attribution](issue-grouping-independent40-score.md). Recover
authentic records first. Any new behavioral run needs a frozen protocol and
separate execution approval if paid.

### T3 — Real cold/warm pilot, offline calculator, and operational controls

**Partly evidenced.** Published [pilot data](../cost/pilot/report.json) records
100 inputs, 112 metered calls, 98 completed, two failures/quarantines, and
US$0.007410287. Cold active time is 588.4346 seconds; elapsed time including
interruptions is 1,581.1901 seconds. The offline calculator runs from saved
usage with editable rates and full-run scenarios. Shared reservations, unknown
outcome holds, and pilot checkpoints are implemented and tested.

**Gap:** The published 0.008029-second warm result is a cache-validation path in
`warm()`. The newer local audit exercises full `execute()` orchestration with
zero paid/transport/socket attempts, but has not been included publicly. Do not
count it as delivered. Main-run recovery records remain absent. Full-run cost
and elapsed time are modeled, not measurements of the full corpus. Unknown
usage and grouping costs remain unknown.

## Working result

### W1 — Ingestion, coverage, and successful classification

**Partly evidenced.** The [saved full ingestion profile](contract-ingestion.json)
accounts for 660,622 records, 13 empty texts, and 159,701 missing app versions.
The release and live API agree on the selected run: 110,000 distinct IDs,
100,229 structurally completed, 1,791 quarantined, 1,457 unresolved, 6,522
pending, and one empty. This meets the explicit 100,000 allowance and Hanif's
stricter accepted-row target.

**Gap:** The same assignment retains full-corpus requirements and a coverage
formula using 660,622 / 660,609 denominators. The unchanged saved checker says
`review_required`, with 550,622 missing IDs. Confirm the intended grading scope;
do not weaken the checker or imply a full-corpus pass. The full source CSV was
not reprofiled during this audit; the saved profile and release copy were checked.

### W2 — Runnable bounded stages, saved handoffs, and demonstrated resume

**Partly evidenced.** Code accepts CSV input for ingestion. The pilot harness
runs distinct label, evidence, verify, group, rank, and memo stages. Durable
queue/cache and budget code bound work and preserve settled IDs. Published
pilot checkpoints and the release's synthetic SIGINT/resume recording provide
limited recovery evidence.

**Gap:** The main grouping step was not a saved arbitrary-input program stage.
The main run lacks contemporaneous before/after checkpoints. **All 76,523 Jev
requests contain one review**, not the instructor-requested ten. Worker
concurrency does not satisfy that requirement. The final evidence configuration
uses up to 25 reviews; the broader historical export includes requests of up to
50. Disclose these scopes. Do not infer historical recovery from a new mock or
warm replay. A rerun is not authorized by this assessment.

### W3 — Reproducible ranking and usable database-backed deployment

**Evidenced.** The release ranking reproduced exactly using `severity_sum`
descending, then issue ID ascending. The published Python
[backend](../dashboard/server.py) serves stored data through its
[database adapter](../dashboard/backend.py) to the live Astro dashboard.
Metrics, 41 issues, checked provisional recommendations, memo, claim filter,
Pipeline section, and aggregate flow are available without rerunning inference.

**Gap:** This establishes operation and arithmetic, not validated product
priorities. Preserve the baseline/public denominators and advisory labels.
The 600-case verifier and 40-case human comparison have the limits above.

## Remaining evidence conflicts

The unchanged saved full-reference checker still reports 7,980 nonaccepted
statuses, 949 nonbinary call outcomes, 79,797 unknown phases, and 94 unavailable
usage fields. The release audit found **47 calls** missing input/output usage;
that is consistent with **94 fields**, not 94 separate calls. Missing role
records, split origins, and absent main checkpoints remain unresolved. This
audit inspected the saved checker report; it did not rerun the full-source
checker or alter the export.

The published [call aggregate](run-110k-calls-aggregate.json) matches the release
log hash and sums to **US$4.725972366**: Jev US$3.264536184 and evidence
US$1.461436182. The README's roughly US$4.2 and its US$2.92 / US$1.29 split use
a different earlier scope. Reconcile and name the scopes before submission.
Neither figure proves the complete project bill: unresolved reservations and
unrecorded grouping usage are not zero. Summed request durations are not wall time.

## Local work: inclusion decisions, not delivered evidence

These files were found in the preserved local worktree and are absent from
current main and the grading ZIP. Human answer sheets were not opened.

| Prepared local item | Verified state | Publication or inclusion decision |
| --- | --- | --- |
| `reports/product-decision-memo-2026-10-13.md` | Expanded decision memo exists locally. Published memo remains the short provisional version. | Hanif/reviewer chooses whether to include the expanded alternative/measurement discussion after claim review. Helps D4. |
| Human20 packet | Private preparation directory and source/human-sheet workflow exist. Answer completion and correctness were not inspected. | Keep answers private. Decide whether to complete a new holdout and include only approved method and aggregate results. Helps T1; not a replacement for the original 50. |
| Full warm audit | Local tool hash matches its saved aggregate report. Report records all six stages, unchanged 112 calls/254 outputs, and zero new paid/transport/socket attempts. | Review and include a text-only method/report if approved. This is a separate new replay, not historical main-run recovery. Helps T3/W2. |
| `reports/remediation-plan-2026-10-13.md` and transport | Local plan and mock-tested adapter exist. They are not published execution evidence. | Decide which free checks to include. Paid work requires fresh approval and billing checks. Do not treat prepared requests as completed tests. Helps T1/T2/T3. |

## Checks run for this assessment

- `python3 -m unittest discover -s tests -t . -q`: **413 tests, OK, 2 skipped**,
  in **5.407 seconds**. This was the completed run with local filesystem and
  localhost access. The two private golden-plan tests skip in this clean
  worktree. An earlier restricted run had one localhost socket permission
  error; it is not reported as passing. The permitted rerun resolved it.
- `python3 -m spotify_pipeline --help`: passed.
- `python3 -m tools.cost100_offline_calculator --scenario cost/scenario_full.json`:
  passed without keys or inference. A temporary copy with doubled rates changed
  7,410,287 nanodollars to 14,820,574. Measured times and unknown local compute
  cost were unchanged. `--projected-records 100000` left measured pilot results
  unchanged.
- Release audit: 110,000 unique IDs, 30,400 unique memberships, all 41 baseline
  ranks and all 164 claims recomputed; live claims equal the release. No answer
  scoring, new model execution, or full-source checker rerun was performed.
- Browser checks: live memo filter, Pipeline, sample-only Verify state, and
  complaint-flow section verified. Aggregate API checks and the explicit flow
  alias comparison are described above.
- Local report links and whitespace checks passed. Removing the one added first
  line from the old benchmark produces exactly its original bytes. README edits
  change only the two rubric pointers. Twelve recorded public files in the
  original worktree retain their pre-audit hashes.

## Prioritized actions through 21 October

Proposed owners below are assignments to confirm, not messages already sent.
Zero-cost work comes first. No action here authorizes spending, publication,
new labels, deployment, or submission.

| Order / target | Action and criterion helped | Owner | Acceptance check | Paid calls? | New human labels? |
| --- | --- | --- | --- | --- | --- |
| 1 · 15–16 Oct | Confirm deadline and 100k/full-corpus scope. W1, D1. | Hanif + instructor | Written clarification linked; unchanged checker limits retained. | No | No |
| 2 · 16 Oct | Reconcile cost scopes, one-review batching, old architecture prose, and local/published wording. D1, D2, T3, W2. | Claude/cost owner + coordinating reviewer | Every reported total names its source and scope; no claim that Jev used ten reviews. Published diagrams stay described as published. | No | No |
| 3 · 16–17 Oct | Review the expanded memo and full warm audit for inclusion. D4, T3. | Hanif + reviewer | Approved public text has checked numbers, alternatives, limits, and warm replay scope; no private answers or source text. | No | No |
| 4 · 16–18 Oct | Recover genuine verifier inputs/predictions, call receipts, and checkpoint backups. D2, T2, W2. | Original grouping/verifier owner | IDs/hashes/configuration and creation order link authentic records; absent fields remain unknown. | No | No |
| 5 · 17–18 Oct | Re-run deterministic grading/ranking, calculator sensitivity checks, links, and fresh-checkout tests after approved integration. D1, D3, T3, W3. | Codex/reviewer | Stable ranking and claims; rate edits affect spend only; test results and remaining checker flags saved. | No | No |
| 6 · 18–19 Oct | Inventory existing T1 diagnostics; report missing quote/entity/review-flag measures. T1. | Evaluation reviewer | Aggregate-only inventory distinguishes measured, unscored, ambiguous, and answer-influenced cases. | No | No |
| 7 · By 20 Oct | Prepare the final evidence map and public URL package; recheck live read-only routes. D1, W3. | Hanif + reviewer | Accessible artifacts, checksum match, current disclosures, and submission-ready README by the earlier documented deadline. | No | No |
| 8 · 18–20 Oct, only if chosen | Complete the separate human20 holdout and needed semantic annotations. T1. | Hanif / independent human reviewer | Human answers stay private; frozen predictions precede scoring; original 50 retained; overlap and uncertainty disclosed. | No for labeling; model predictions may need separate approval | Yes, if not already completed |
| 9 · 19–20 Oct, only if approved | Obtain real independent/planted/injection outcomes under the frozen bounded plan. T2. | Execution owner + reviewer | Blind inputs exclude first/human answers; outputs and usage saved; actual failures and planted detections reported. | Yes for the prepared API route; explicit approval required | Only if human-reference scoring is included |
| 10 · By 21 Oct, if extension confirmed | Submit the approved public repository URL through the course portal. D1. | Hanif | Submission receipt saved before 23:59 Pacific; use 20 Oct if the extension is not confirmed. | No | No |
