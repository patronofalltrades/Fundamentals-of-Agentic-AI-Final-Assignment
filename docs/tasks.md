# Coordination record

The local clone is the shared project record. Read this file and `AGENTS.md`
before taking a task. Check the branch, status, and origin first.
This file is a manual task record. It is not a lock or a running agent service.

## Current work — October 5, 2026

| Task | Actual owner | Branch / worktree | Status | Artifacts and handoff |
| --- | --- | --- | --- | --- |
| Offline Python foundation | DeepSeek through OpenCode CLI; Codex reviews and integrates | `feat/offline-foundation` / this checkout (`.`) | Complete locally; ready for review | `spotify_pipeline/`, `cost/`, `tests/`, implementation notes. Two DeepSeek passes completed. Independent review fixes added. 134 synthetic tests pass. |
| Coordination and diagram | Codex coordinator | `feat/offline-foundation` / `.` | Complete locally | Root `AGENTS.md`, this record, `docs/architecture.md`. OpenCode CLI is the coding route. No other agents are assigned or contacted. |
| Full-source offline ingestion | Codex coordinator | `feat/offline-foundation` / `.` | Complete | 660,622 rows. Core profile matches the course helper exactly. 118.151 seconds. 660,609 pending nonempty texts; 13 empty quarantines. See `reports/`. SQLite state is ignored. No classification calls. |
| Coding-route correction | Codex coordinator | `feat/offline-foundation` / `.` | Complete locally | Updated instructions, diagram, README, provenance, tracker and project config. Exact OpenRouter ID verified by `opencode models openrouter`. No inference run. |
| Review and publication | Coordinating reviewer | No integration branch selected | Pending review | Review the local diff and tests. Local implementation commit is authorized. Push is not authorized yet. |
| Human golden labels | Unassigned human | No branch assigned | Pending | Human answers and overlap policy. Labels must remain outside model inputs. |
| Runtime model access and pilot | Unassigned | No branch assigned | Pending | Verify classification/verifier routes. Approve budget. Run real cold/warm 100 before 500, 10,000, and full corpus. |

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
The implementation is not pushed. Central review and integration remain pending.

## Taking another task

Agree on the task owner and file scope first. Record the branch and worktree.
Use a separate worktree for each simultaneous coding agent.
Do not edit another owner's files without a handoff.
Review and integrate centrally after the checks pass.
Keep unrelated user changes. Do not reset, force-push, or publish without permission.

## Handoff requirements

Record the exact commit, changed files, commands run, results, and remaining gaps.
Distinguish synthetic checks from real data and real model runs.
No runtime classification, real pilot, ranking, or memo exists yet.
The cost scaffold has unknown measurements and prices.
Full-run projections and live spend/recovery controls remain pending.
The runtime budget must stay strictly below US$50. A ceiling is not spending approval.
