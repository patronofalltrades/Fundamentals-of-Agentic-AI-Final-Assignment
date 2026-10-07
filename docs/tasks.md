# Coordination record

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
