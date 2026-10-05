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
The 100-review pilot has saved labels, exact evidence, and complete local classifications. Ranking and memo do not exist yet.
The separate cost scaffold still lacks full cold/warm stage measurements and projections.
Full-run projections and live spend/recovery controls remain pending.
The runtime budget must stay strictly below US$50. A ceiling is not spending approval.

Class 7: October 13, 2026; time not supplied. All 50 rows have human entries,
and the CSV export has passed mechanical checks; real evaluation remains pending. Check process activity live before another run. Parent owns Space updates; each completed milestone is reported
with files, commit, checks, and blockers before publication.
