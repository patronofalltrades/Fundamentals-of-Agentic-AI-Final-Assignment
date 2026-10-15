# Submission closeout handoff — 15 October 2026

Owner: Codex. Branch: `docs/submission-closeout-current-2026-10-15`.
Base: `2a725dcc3aca6f5882142c106141629274065cd9` (merged PR #31).
This report's containing commit is the local handoff. Publication is not
authorized. The original worktrees, cost files, and private results are preserved.

## Verified outcomes

- PR #30 (`44928e1`) and PR #31 (`2a725dc`) merged. Their automatic Production
  deployments succeeded at 17:11:14 and 17:17:15 UTC respectively. A final
  read-only main check still returned `2a725dc`. No manual deployment ran.
- The live summary has 110,000 selected and 100,229 accepted. The live memo
  retains 164 claim lines and correctly attributes the displayed 40% comparison
  to assistant manual assignments. The expanded memo and full warm audit are
  published GitHub reports; the dashboard retains the short provisional memo.
- Older grouping files were recovered and matched published hashes. Manual
  assignments report 16/40 exact and 21/40 family; the separate archived agent
  labels report 16/40 exact and 22/40 family. No answers were inspected or
  scoring rerun. Production accuracy and blind execution remain unproven.
- Known main-run charges reconcile exactly: scale US$4.213915344 plus earlier
  checkpoints US$0.512057022 equals US$4.725972366. Null charges on 46 calls and
  missing usage on 47 calls remain unknown. This is not the full project bill.
- The unchanged official checker reran with no golden input. It remains
  `review_required`, with the same coverage and issue counts. All 11
  manifest-pinned candidate files retained their hashes. All 12 release members
  equal the candidate. No grading rule or saved result was changed.
- The current assessment now marks D1/D4 evidenced and T3 partly evidenced.
  The original audit date and checks are retained. The ten-criterion checklist
  separates closed publication gaps from remaining semantic/provenance limits.
- The supported deadline is **20 October 2026, 23:59 Pacific**, from the current
  assignment document and the coordinating task's course-announcement check.

## Checks completed

| Check | Result |
| --- | --- |
| `python3 -m unittest discover -s tests -t . -q` | 413 tests in 7.557 seconds; OK, 2 skipped |
| `python3 -m spotify_pipeline --help` | Passed |
| `node --test web/tests/privacy.test.ts` | 1 test passed |
| `node --check dashboard/static/app.js` | Passed |
| Offline calculator with `cost/scenario_full.json` | Passed; measured API cost 7,410,287 nanodollars |
| Temporary doubled-rate input | 14,820,574 nanodollars; recorded cost and measured timings unchanged |
| 100,000-record projection | Measured pilot unchanged; local compute cost remains unknown |
| Unchanged full-reference course checker | Completed; `review_required`, unchanged flags |
| Changed Markdown relative links and aggregate JSON parsing | Passed |
| Changed-file private-path/credential-marker scan and `git diff --check` | Passed |

The Python skips are the private golden-plan tests in the isolated checkout.
Checks used this connected Mac. No new inference, paid calls, scoring, human
label collection, push, PR, merge, public upload, or submission was performed.
Detailed checker output and ledger aggregates remain ignored, mode 0600.

## Exact changed-file list

1. `AGENTS.md`
2. `README.md`
3. `docs/implementation.md`
4. `docs/tasks.md`
5. `reports/cost-scope-reconciliation-2026-10-15.md`
6. `reports/evaluation-attribution-and-inclusion-2026-10-15.md`
7. `reports/final-submission-checklist-2026-10-15.md`
8. `reports/grading-closeout-2026-10-15.md`
9. `reports/grouping-score-provenance-2026-10-15.md`
10. `reports/issue-map-blocker-triage-2026-10-12.md`
11. `reports/issue-map-independent-validation-2026-10-12.md`
12. `reports/rubric-assessment-2026-10-16.md`
13. `reports/submission-closeout-checks-2026-10-15.json`
14. `reports/submission-closeout-handoff-2026-10-15.md`

## Remaining decisions and blockers

The full-corpus checker scope, incomplete selected rows, missing historical
checkpoints/phases and role receipts, split provenance, one-review Jev payloads,
and incomplete semantic/behavioral evaluation remain disclosed. No failed gate
is presented as repaired. Full warm reproduction needs the private pilot DB.

Automatic approval review rejected an optional direct check of private reference
review text for the single empty row. No status adapter ran. Separate approval
for that bounded code-only validation is needed before considering a one-row
format adapter. This does not block the completed aggregate closeout.

Publication of this local commit and any versioned release-memo addendum need
approval. The frozen release still contains its earlier prose. Ask the cost
owner to qualify the historical evidence maximum of 50 versus the scale maximum
of 25. Cost files were not edited here.

The optional human20 next steps are in the
[final checklist](final-submission-checklist-2026-10-15.md). Its expected CSV was
absent; workbook completion was not inspected. The original 50-case evaluation
remains complete. Hanif submits the approved repository URL and keeps the receipt.
