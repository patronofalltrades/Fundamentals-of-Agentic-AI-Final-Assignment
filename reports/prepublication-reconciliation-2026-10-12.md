# Prepublication reconciliation — 12 October 2026

This is a local, text-only preparation record. No branch was merged or pushed.
No database was written. No model, paid, deployment, upload, or recording action
occurred. Private review IDs, texts, answer rows, and credentials stay outside
this report.

## Main divergence and integration hold

The GitHub `main` ref and the local `gh/main` ref both point to `d14ca59` at
this check. This isolated branch starts at `68104f9`; their merge base is
`dc36789`. Main has 57 commits absent here, and this branch has 107 commits
absent from main. Of 88 paths edited on both sides, 11 have different final
contents. A read-only merge preview finds textual conflicts in `AGENTS.md`,
`README.md`, and `docs/tasks.md`. The README on main still says only nine
golden predictions and no grading export; this branch has the later 50-case
score and grading evidence. Main also has newer dashboard presentation changes
that should be preserved. The expected new cost commit is not yet on GitHub
main. Integration is held for owner review of the three document conflicts and
the resulting dashboard diff. No merge resolution was guessed.

The proposed publication destination, after explicit approval and integration
review, is the GitHub repository
`https://github.com/patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment.git`,
branch `feat/grouping-v4-integration`. This checkout's `origin` instead points
to a local comparison checkout. The proposed branch does not yet exist on
GitHub. No push command was run.

## Unchanged checker: every remaining flag

The saved full-source checker result is `review_required`, with no automatic
grade. Its report and all 11 named candidate input hashes match saved files.
The report uses the unchanged 660,622-ID full-source reference. No checker
rule or source output was changed here. Each remaining issue is disclosed:

| Checker issue | Count | Disposition |
| --- | ---: | --- |
| `missing_records` | 1 flag; 550,622 IDs | Disclosed scope gap: 110,000 selected IDs versus 660,622 required by the unchanged contract. |
| `run_manifest_mismatch` | 1 | Disclosed selected-run versus full-source scope mismatch. |
| `unfinished_classification` | 1 | Disclosed: 7,980 selected rows remain in nonaccepted states. |
| `invalid_status` | 7,980 | Preserve the saved nonaccepted statuses; no false completion or quarantine conversion. |
| `invalid_call_outcome` | 949 | Preserve authentic partial, quarantined-metered, and uncertain outcomes; no unsupported binary mapping. |
| `invalid_run_phase` | 79,797 | Historical initial/resume phase is unknown and remains null. |
| `invalid_usage` | 94 | Unavailable provider usage remains null, not zero. |
| `unlogged_completed_records` | 1 flag; 20,938 rows | Saved label and evidence origins are split or indirect; the checker cannot represent them as one direct origin. Preserve both origins. |
| `missing_model_roles` | 1 | Historical verifier, grouping, and memo provider call records are unavailable. |
| `resume_call_evidence` | 1 | Historical request tables and resume logs lack per-call phase proof. |
| `resume_snapshot_mismatch` | 1 | Authentic main-run before/after snapshots are absent; the separate 100-review pilot checkpoints cannot replace them. |
| `unreadable_file` | 2 | The two absent main-run checkpoint files cannot be supplied from saved evidence. |

The checker reported no ingestion, completed-record schema, membership,
ranking, or numeric-claim flag. The 100,229 accepted rows exceed Hanif's
100,000 accepted-evidence target, but that does not clear the full-source
grading contract. Historical gaps require authentic new evidence or an
instructor-confirmed grading scope; a synthetic repair would misstate the run.

## Golden aggregate to dashboard: prepared, not imported

The frozen source-only file has 50 distinct completed predictions, all with
the same label configuration as the local public-release database:
`0bda2b8478fab805c56f033227017f6f37da9feb7da6b6a79b98b859cb10c647`.
The saved aggregate has 50 human rows, zero missing predictions, topic 0.52,
intent 0.76, joint 0.28, and severity MAE 0.56. The detailed aggregate has
30/50 exact severity, giving severity agreement 0.60. Twelve human rows ask
for review. The set has development-text overlap and possible earlier golden
influence. These are diagnostics, not population accuracy.

`dashboard.evaluation.evaluation_record` accepted an in-memory adapter with
`label_set=original`, `approved_cases=50`, `total_cases=50`,
`missing_or_invalid_predictions=0`, agreement `{topic: 0.52, intent: 0.76,
severity: 0.60, joint: 0.28}`, `severity_mae_on_valid_predictions=0.56`,
`official=false`, the label configuration above, a nonempty benchmark version,
and the recorded completed-human-CSV SHA-256
`ff084828aa2d88970e70508dd36362aaaade3d48a1d1ee1d09503e24ffaeb0f6`.
That human-file digest is recorded in `docs/human_evaluation.md`; it was not
rehashed in this task. The saved evaluation aggregate cannot be passed
directly to `import-evaluation`: it lacks `label_configs`, `agreement`,
benchmark metadata, and `official`. A safe adapter must derive only these
aggregate fields and recheck the human-file digest before use.

The current evaluation page says its scorer is the unchanged course
`score_gold` checker. This 50-case score came from the isolated
`tools/evaluate_human_labels.py` evaluator. Before public import, either run
the unchanged scorer on the same frozen predictions using code-only access to
the human file, or correct the page's scorer attribution and add the overlap,
review, and independence limits. The current page does not display
`official=false`, so that value alone does not communicate the limitation.

After the page and payload are reviewed, the intended write command is
`python3 -m dashboard import-evaluation --report <private-adapted-report.json> --label-set original --postgres-env DASHBOARD_DATABASE_URL`.
The environment variable must point to the intended production dashboard
database, and the command must only run with publication approval. It stores
summary fields under `dashboard_meta.evaluation:original`; no case-level rows.
Verify afterward through read-only `/api/evals` and `/api/summary`: all four
agreements, severity MAE, 50/50 coverage, `official=false`, matching
configuration, and no private IDs or text. The database's current evaluation
keys are empty. No import command was run.

## Optional catalog and memo

The approved 41-issue catalog is already frozen in `docs/issue-catalog-v1.json`
at SHA-256 `8c73e62059e86aea48b94da0d4b0bf86df048e0d83442e1ce4bf7b44dc105111`.
The provisional memo already exists at
`reports/provisional-product-priority-memo.md` and matches the private grading
memo at SHA-256 `e839f30aa39adc9db49b688a205bc7fbd7ae468bf711e6640c27658d09bc68d7`.
Its numeric claims were checked against saved ranking; semantic membership
remains advisory. A new catalog freeze or duplicate memo is unnecessary.
