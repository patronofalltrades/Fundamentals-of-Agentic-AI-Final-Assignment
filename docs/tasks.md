# Coordination record

## Bounded measurement completion — 15 October 2026

Owner: Codex, `feat/bounded-measurement-followup`, isolated
`spotify-rubric-pr33` worktree. Scope: `tools/bounded_gap_followup.py`, its
synthetic tests, and this record. The display fix was published in PR #36.
New paid results remain local pending a publication handoff.

Hanif explicitly approved a separate one-time US$0.38 allowance at 23:22:06 UTC,
independent of the old US$49.99 project ceiling. Source sharing was approved at
23:08:14 UTC. This covers only five frozen ten-review batches through OpenRouter
to Crusoe, at most two attempts per batch and ten total. Preserve old costs,
holds and outputs. Keep the existing provider caps. Stop on uncertain delivery.
No production database writes, grading release changes or course submission.

## Measurement status follow-up — 15 October 2026

Owner: Codex, `feat/measurement-status-scope`, existing isolated
`spotify-rubric-pr33` worktree. Base: deployed PR #35, `0034e20`.
Scope: distinguish saved measurements from missing evidence in the evaluation
registry and cards; affected tests; one bounded paid follow-up and this handoff.
The seven affected cards now say Measured locally, with coverage, billing and
historical gaps always visible. All numerical metrics and source fingerprints
are unchanged. Python: 431 tests, two skips; frontend: build, typecheck and four
Node tests passed using identical source and pinned dependencies restored from
the existing offline cache. The original dependency tree stalled on file reads.

Hanif approved the five-batch US$0.38 run and source-data sharing on 15 October.
No inference has run: project-wide headroom remains unverified because omitted
historical costs have no upper bound. See the
[follow-up report](../reports/measurement-status-followup-2026-10-15.md) and
[read-only budget check](../reports/project-headroom-preflight-2026-10-15.json).
No human20, push, merge, deploy or production database writes.

## Production measurement audit — 15 October 2026

Owner: Codex, `feat/production-measurement-audit`, isolated `spotify-rubric-pr33`
worktree, based on merged PR #34 main `65d1396`. Scope: public measurement
coverage arithmetic and aggregate report, evaluation registry/API/UI, regression
tests, and a measurement-gap inventory. Preserve historical reports, cost files,
private answers, original databases and attribution. No paid calls, human20,
production database writes, push, merge or deployment are authorized.

Local result: completed measurement inventory and source/config-scoped sample
display fixes. New full-warm replay: six stages, zero paid/transport/socket
attempts, original database unchanged. Checks: 430 Python tests (428 passed,
two private-plan skips), four Node tests, CLI and generated-report checks.
Follow-up: the authorized lockfile-only dependency restore completed; Astro
build and 36-file typecheck passed. No package/lockfile changes. The closure plan
records verified source availability, current provider prices and bounded paid
options; none is approved or executed.
See `reports/production-measurement-audit-2026-10-15.md` for remaining evidence
gaps and publication approval boundaries.

## Submission closeout — verified 15 October 2026

Owner: Codex, `docs/submission-closeout-current-2026-10-15`, isolated
`spotify-submission-closeout` worktree. Base: merged PR #31 main `2a725dc`.
PR #30's memo/warm/attribution artifacts and PR #31's cost/architecture edits
are preserved. Scope: aggregate provenance and cost reports, unchanged-checker
verification, current assessment, deadline, entry-point notes, and final
submission checklist. Existing `cost/` files and private saved results stay
unchanged. No new inference, answer inspection, publication, or manual deployment.
See [the checklist](../reports/final-submission-checklist-2026-10-15.md).

## Local attribution and inclusion review — 15 October 2026

Owner: Codex, branch `docs/evaluation-attribution-memo-warm`, isolated worktree
`spotify-attribution-closeout`, based on published main `1217b47`.
Scope: public 40% evaluation wording, the existing expanded memo, the existing
full warm audit tool and aggregate reports, and a text-only review handoff.
No existing cost files, source data, human answers, scores, or release artifacts
are changed. Original worktrees remain preserved. Publication awaits Hanif's
approval. See [the handoff](../reports/evaluation-attribution-and-inclusion-2026-10-15.md).

## Claude handoff — 13 October 2026

Branch `docs/readme-rubric-benchmark`, from `main` at `cec5be9`. Owner: Claude (cost, dashboard, README).

- **Changed files:** `README.md`, `cost/README.md`, `cost/scenario_full.json`, `cost/pilot/*`,
  `tools/cost100_offline_calculator.py`, `tests/test_cost100_calculator.py`, `tests/test_golden_gap_runner.py`,
  `reports/rubric-benchmark-2026-10-13.md`, `reports/cost100-offline-checks.json`.
- **Cost calculator:** it adds full-run estimates from `cost/scenario_full.json`, with no model call. The
  measured pilot results are unchanged.
- **Pilot files:** `cost/pilot/` holds the unredacted pilot files with the 100 review IDs, as Hanif approved.
- **Tests:** two golden-gap tests skip without the private plan in `local/`.
- **Grading release:** release `grading-2026-10-13` holds `grading-110k.zip` and the synthetic resume video.
  Hanif approved it and runs the publish command.
- **Checks:** the full suite passes offline, and the calculator runs with no key.
- **Remaining:** Hanif submits through bCourses. A real-data resume recording is optional.

## Final merge authorization and checks — 13 October 2026

Hanif approved the normal GitHub merge of `feat/grouping-v4-integration` into
main and its resulting Vercel deployment. Codex owns this bounded closeout in
`spotify-v4-worktree`. Main was checked at `00ad910`; there were no newer
commits to reconcile. Final checks passed 408 Python tests, CLI help, the
offline cost calculator, and the web privacy test. Claude's cost artifacts and
main's dashboard, memo, and polish files were preserved. No private files are
tracked. The only web change is the reviewed evaluation attribution component.

The golden-50 aggregate is already imported and verified live. See the dated
README handoff and `reports/final-release-handoff-2026-10-12.md`. The unchanged
full-source grading checker remains `review_required`. Course submission is
pending. The earlier ownership records below describe their original dates.

PR #22 completed the normal main merge at `6a3118f` on 13 October. Its
GitHub-triggered Vercel production deployment reached READY with a successful
GitHub status. Post-deployment API fingerprints, 100,229 accepted rows, and
golden-50 scores were unchanged. Chrome confirmed the attribution and limits.
The README and release handoff record this completed integration.

## Current integration — 12 October 2026

The 100,000-review pipeline integration is owned by Codex on
`feat/grouping-v4-integration` in the separate `spotify-v4-worktree` checkout.
Its scope is the frozen v4 catalog, correction and ranking code, provisional
memo, 100k-focused README, private grading handoff, and pipeline tests. The
private handoff stays ignored under mode-0600 `local/`. The dashboard/API patch
was built by a different task on `fix/dashboard-100k-provisional` at `43fabf7`.
Its 84 dashboard-only tracked files were copied byte-for-byte into this branch;
the six differing shared project files were kept from the pipeline branch.
The shared canary and Claude's dashboard checkout remain unchanged by this
integration work. No push, merge, or deployment has been authorized.

The v4 branch ran 315 offline Python tests successfully. The ranking remains
advisory. The separate assistant manual comparison agreed with human answers
on 16/40 (40.0%); this did not evaluate the production grouping model. The 40
human decisions were subsequently used as overrides. The combined branch then
passed 386 Python tests with localhost access, the web privacy test, Astro
typecheck, and static build. See
`reports/grouping-v4-handoff.md` and `reports/submission-status-2026-10-12.md`.

The local clone is the shared project record. Read this file and `AGENTS.md`
before taking a task. Check the branch, status, and origin first.
This file is a manual task record. It is not a lock or a running agent service.

## Current work — October 5, 2026

| Task | Actual owner | Branch / worktree | Status | Artifacts and handoff |
| --- | --- | --- | --- | --- |
| Offline Python foundation | DeepSeek through OpenCode CLI; Codex reviews and integrates | `feat/offline-foundation` / this checkout (`.`) | Complete locally; ready for review | `spotify_pipeline/`, `cost/`, `tests/`, implementation notes. Two DeepSeek passes completed. Independent review fixes added. 135 synthetic tests pass after local review. |
| Coordination and diagram | Codex coordinator | `feat/offline-foundation` / `.` | Complete locally | Root `AGENTS.md`, this record, `docs/architecture.md`. Alfred is OpenAI Dots; Sol is ChatGPT. OpenCode CLI is the coding route. No other agents are assigned or contacted. |
| Full-source offline ingestion | Codex coordinator | `feat/offline-foundation` / `.` | Complete | 660,622 rows. Core profile matches the course helper exactly. 118.151 seconds. 660,609 pending nonempty texts; 13 empty quarantines. See `reports/`. SQLite state is ignored. No classification calls. |
| Coding-route correction | Codex coordinator | `feat/offline-foundation` / `.` | Complete locally | Updated instructions, diagram, README, provenance, tracker and project config. Exact OpenRouter ID verified by `opencode models openrouter`. No inference run. |
| Local foundation review | Sol via ChatGPT | `feat/offline-foundation` / this checkout (`.`) | Complete locally | Reviewed course contracts, code, reports and exclusions. Fixed unresolved token usage, unset cap admission, backup name reuse and verifier diagram input. See `docs/local_review.md`. Integration and publication remain pending. |
| Review and publication | Coordinating reviewer | No integration branch selected | Pending review | Review the local diff and tests. Local implementation commit is authorized. Push is not authorized yet. |
| Human labeling setup and prices | Codex coordinator | `feat/offline-foundation` / `.` | Complete locally | Blank source verified and isolated working copy made. Dated provider quote reference saved. GLM removed from current plan. Class 7 date recorded; time unknown. |
| Manual-label workbook and exporter | Sol via ChatGPT | `feat/offline-foundation` / this checkout (`.`) | Complete locally | Hanif filled all 350 cells. With explicit authorization, the assistant corrected only case/whitespace in four selected exact quotes after unique source-span checks. Backup saved outside repo. Exported 50 valid rows; CSV and workbook remain outside Git. |
| Human scoring guide | Sol via ChatGPT | `feat/offline-foundation` / this checkout (`.`) | Complete locally | Course-aligned severity 1–5 and optional sentiment anchors added to `docs/human_evaluation.md`; README points to it. The guide task did not edit answer files. |
| Human golden labels | Hanif | Outside repo | Mechanically validated; semantic quality unreviewed | Completed CSV has 50 rows and 350 valid answer fields. All source fields match. SHA-256 `ff084828aa2d88970e70508dd36362aaaade3d48a1d1ee1d09503e24ffaeb0f6`. No expected answers were sent to a model or committed. |
| Offline evaluation boundary | Sol via ChatGPT | `feat/offline-foundation` / this checkout (`.`) | Implemented with synthetic checks; real evaluation pending | Aggregate-only evaluator gates on complete source-matched human CSV and saved predictions. Direct CLI invocation works from repo root. Runtime source CSV parser rejects answer columns. 142 total offline tests pass. No real predictions exist. |
| Jev enrichment and bounded pilot runner | Codex | `feat/jev-enrichment` / `../jev-enrichment-worktree` | Implemented and used for label pilot | Typed Choice/Score labels, persistent pre-call reservations and usage ledger, exact-text cache, offline replay. See `docs/jev_enrichment.md` and aggregate `reports/jev-pilot-100.json`. |
| Jev `cost_100.csv` label pilot | Codex | `feat/jev-enrichment` / ignored `local/jev_pilot.db` | 100 labels complete | Hanif entered the existing key privately in Terminal. 100 settled calls, no retry, 87,887 input and 19,656 free output tokens, USD 0.003691254 usage-derived cost under USD 0.60 cap. Source IDs/hashes and label schema pass. See `reports/jev-pilot-100.json`. No top-up or fallback. Cold wall time was not persisted. |
| Evidence and completed import | Codex, separately authorized by Hanif | `feat/jev-enrichment` / ignored local databases | 100 saved; structural checks passed | The earlier automatic approval rejection preceded a later authorized extraction. The local pilot ledger now has 100 evidence records; the separate sample database has 100 completed classifications. Source identity, exact spans, and output schema pass offline checks. Saved evidence uses prompt v1 for 90 rows and v2 for 10. No semantic accuracy or human agreement is claimed. |
| Entity boundary repair and pilot report | Codex (authorized by Hanif) | `fix/jev-entity-boundaries` / `2026-10-06/task/jev-entity-boundaries` | Integrated locally on `feat/offline-foundation` at `e24c3c6`; publication pending | Scope: `spotify_pipeline/codex_evidence.py`, `tests/test_jev_pilot.py`, `README.md`, `docs/jev_enrichment.md`, this tracker, the bug note, and `reports/jev-pilot-100.json`. Copied the two preexisting uncommitted Jev files into a separate worktree, then added entity boundary validation, synthetic regression tests, and a read-only offline warm replay. Original Jev worktree and saved outputs are untouched. Canonical integration passed 158 offline tests and read-only validation of 100 records. See `docs/jev_entity_boundary_bug.md`. |
| Jev topic rubric v2 | Codex (approved by Hanif) | `fix/jev-topic-rubric-v2` / `2026-10-06/task/jev-topic-rubric-v2` | Integrated locally on `feat/offline-foundation` at `a7b6f7d`; publication pending | Scope: `spotify_pipeline/jev.py`, `spotify_pipeline/jev_import.py`, Jev tests, README, `docs/jev_enrichment.md`, this tracker, and `docs/topic_rubric_v2.md`. Keep eight labels, clarify contract routing and tie-breaks, bump prompt version, and reject v1 results under v2 configuration. Historical pilot data stays v1. Canonical integration passed 161 offline tests, CLI help, and a 100-review dry run with zero model calls. The exact-text overlap and future 50-case evaluation strata are recorded in the rubric note. |
| Jev v2 versus v1 on `cost_100.csv` | Hanif launched; Codex compared and finished evidence | `feat/jev-rubric-v2-comparison` / `2026-10-06/task-2/spotify-v2-comparison` | 100 v2 labels and evidence complete locally; review pending | See `reports/jev-rubric-v1-v2-100.md` and `.json`, `reports/jev-v2-evidence-100.json`, and separate ignored ledgers. Both Jev runs have 100 settled attempts, no retry; combined usage-derived Jev cost USD 0.007953708. Topics changed on 32 rows. Historical v2 wall time remains invalid; in-process monotonic timing is repaired. The v2 evidence working copy has 24 strict v1 reuses with original provenance and 76 new ChatGPT-auth Codex results after direct user authorization; 76/76 succeeded, with 467.882031003 summed attempt seconds. Codex tokens/cost and stage wall time are unknown. Exact source/evidence validation and separate offline import completed 100/100 classifications. No golden evaluation, push or 500-review expansion. |
| V2 metrics and development review | Codex | `feat/jev-rubric-v2-comparison` / `2026-10-06/task-2/spotify-v2-comparison` | Implemented locally; review pending | Future Codex JSON usage counts and whole-stage monotonic timings are saved only when observed; historical unknowns stay null. Synthetic cold/warm no-network harness covers ingestion through memo stubs, cache and import. Manual fixed-contract review records one likely catalog model miss; the skip-limit case fits usability. See `docs/jev_v2_instrumentation_review.md`. No model calls, human answers, 500 run, or push. |
| Frozen v2 checkpoint 500 preflight | Codex | `feat/jev-rubric-v2-comparison` / `2026-10-06/task-2/spotify-v2-comparison` | Completed before live checkpoint | Supplied 500-row source and manifest verified. Separate ignored checkpoint ledger reused the first 100 exact v2 source rows, labels and evidence. Of 400 remaining IDs, 379 distinct new texts needed direct calls. Jev ledger cap USD 0.596308746 reserved measured v1 USD 0.003691254 within the cumulative USD 0.60 bound. User approved sending the 400 texts to TypeSafe and OpenAI Codex on October 6. The hidden-input launcher let Hanif provide the existing key. See `docs/checkpoint_500_preflight.md`. |
| Jev/Codex checkpoint 500 execution | Hanif launched Jev; Codex completed evidence and offline import | `feat/jev-rubric-v2-comparison` / `2026-10-06/task-2/spotify-v2-comparison` | 500/500 labels, evidence, and canonical classifications complete locally; assignment readiness hold | Jev: 379 new settled calls, 384,476 input tokens, USD 0.016147992 new charge and USD 0.024101700 cumulative with v1/v2, 127.023306667-second label-stage wall. Codex: 379 new successful review calls, 21 exact-text evidence reuses, 6,955,138 reported new input tokens. A local preflight failure and an interrupted unknown-delivery attempt remain recorded; the latter was retried once and linked. Codex incremental cost and full evidence wall are unknown. Offline import accepted 500/500; 177 offline tests passed. See `reports/checkpoint-500-readiness.md` and `.json`. No gold evaluation, verifier, grouping, ranking, memo, grader export, 100,000-row inference, or push. |
| Model decision and timing plan | Hanif (decision); Claude (Line A) wrote the record | `feat/jev-rubric-v2-comparison` / this checkout | Decided 2026-10-06; plan not yet implemented | `docs/jev_decision_and_timing.md`: keep Jev (frozen v2), full-corpus scope, batched Jev requests and code-built evidence with capped Codex as timing mitigations, gates with dates, local and hosted alternatives measured or quoted and not chosen. No code, ledger or report was changed. |
| README rewrite in STE | Hanif requested; Claude (Line A) wrote it | `feat/jev-candidate-prototype` / this checkout | Done locally 2026-10-07; not pushed | `README.md` now gives status, decisions, measured results, risks, next gates, run commands, golden-label notes, data inventory, required outputs, layout, rules and limits in short STE sentences. Facts were checked against saved reports. Stale lines were removed: blank golden labels, no model commands, pending human labels. No code, ledger or report was changed. |
| Fix list for Codex (7 Oct) | Hanif (owner); Claude (Line A) wrote it | local commit on `feat/jev-candidate-prototype`; start each fix from GitHub `main` 3272c8f | **Open — read first** | `docs/fix_list_2026-10-07.md`: private paths in 4 files; invalid v2 timing/status labels; batched Jev; evidence route; verifier, grouping, ranking, claims, memo and grading export; true cold/warm pilot and calculator; interrupt/resume; `needs_review` rule; golden scoring; full-corpus scope; dates. |
| Instructor clarification to `main` | Hanif; Claude (Line A) prepared the pull request | `docs/instructor-clarification` / `Desktop/faai-clarification` | Pull request open | Merges `f88df90` (AGENTS.md clarification) into GitHub `main`. Updates README, `docs/fix_list_2026-10-07.md` and `docs/jev_decision_and_timing.md`: 100,000-review minimum with full corpus as stretch, 10 reviews per request, dashboard deliverable, measured note for the `batch` worktree. After merge, update all fix worktrees from `main`. |
| Jev question-limit check for fix 2.1 | OpenCode (Line A) | `task/jev-question-limit` / `../faai-task-question-limit` | Complete locally; push pending approval | Resolves the fix list 2.1 open question: TypeSafe docs state no question-count cap; real limits are 64k tokens per request and 32k for state plus longest question (Models, API reference, fan-out). Saved Line A ledger `cost/pilot_calls.jsonl` already proves 36 reviews, 180 questions and 32,624 input tokens in one successful `jev-1.13.0` call, so the required bounded test is on record. Note: `docs/jev_question_limit_note.md` — drop the 8-row cap, keep the token guard, pack size in `label_config`, jaggedness caveats (context rot, option order) stay with the 2.1 agreement check. Files touched: new note plus this tracker row. Zero model calls, zero cost. |

The current coding choice is **DeepSeek V4 Flash 0731**, provider **OpenRouter**,
accessed through **OpenCode CLI**. The verified exact ID is
`openrouter/deepseek/deepseek-v4-flash-0731`. Project `opencode.json` records it.
No OpenRouter inference has been run. Current price, billing route, and potential
spend checks are pending before any further inference. No top-ups are authorized.
The two completed build passes used `opencode-go/deepseek-v4-flash-vision-exp`.
Their history is preserved. No new Go calls are allowed. No inference process
is running.
The coding sessions received requirements, code, and synthetic fixtures.
Raw data and golden answers were not sent to them.

Foundation commit: `74e471b8f7fcc3a50c3e6133b5bd57883aa7a27d`.
The coding-route correction is a separate documentation/configuration commit.
The local handoff is the latest commit on `feat/offline-foundation`.
Use `git log -1 --oneline` and `git show --stat HEAD` to inspect it.
See `reports/offline-verification.json` for the checks.
Mermaid structure was checked. No local parser or render test was available.
The Jev repair is integrated locally on `feat/offline-foundation` at `e24c3c6`. It is not pushed; publication review remains pending.

## Taking another task

Hosted extractor benchmark owner: Codex, branch `feat/hosted-extractor-benchmark`
in the isolated `spotify-extractor-benchmark` checkout. File scope:
`tools/openrouter_extractor_benchmark.py`, its hidden-input launcher and
synthetic tests, this tracker, and `reports/openrouter-extractor-benchmark.md`.
One DeepInfra inference succeeded. A second POST lost its connection and has
unknown delivery. The authenticated account check on October 7 found no
visible second bill on the benchmark key; attempt 2 now records that check
while retaining its full reservation. The explicit retry path is prepared.
The live smoke saved three valid results per route. Hanif launched the
100-review continuation; DeepInfra attempt 8 received a billed response but
failed local evidence validation. Its exact validation detail was not saved,
and provider I/O logging was disabled. The runner stopped, kept the full
reservation, and made no automatic retry. The benchmark owner added local
forensic capture for future invalid responses and a synthetic regression.
The runner now skips only confirmed metered row-output failures, including
Groq's specific strict-schema rejection, without accepting or retrying them.
Five consecutive failures pause that route, while isolated failures allow
continued sampling. The read-only plan has 61 untouched DeepInfra rows and
71 untouched Groq rows; no continuation has run after the streak-policy
change. See
`reports/openrouter-extractor-benchmark.md`.

Agree on the task owner and file scope first. Record the branch and worktree.
Use a separate worktree for each simultaneous coding agent.
Do not edit another owner's files without a handoff.
Review and integrate centrally after the checks pass.
Keep unrelated user changes. Do not reset, force-push, or publish without permission.

## Handoff requirements

Record the exact commit, changed files, commands run, results, and remaining gaps.
Distinguish synthetic checks from real data and real model runs.
The 500-review checkpoint has saved labels, exact evidence, and complete local classifications. Ranking and memo do not exist yet.
The separate cost scaffold still lacks full cold/warm stage measurements and complete full-pipeline projections.
Full-run projections and live spend/recovery controls remain pending.
The runtime budget must stay strictly below US$50. A ceiling is not spending approval.

Class 7: October 13, 2026; time not supplied. All 50 rows have human entries,
and the CSV export has passed mechanical checks; real evaluation remains pending. Check process activity live before another run. Parent owns Space updates; each completed milestone is reported
with files, commit, checks, and blockers before publication.
