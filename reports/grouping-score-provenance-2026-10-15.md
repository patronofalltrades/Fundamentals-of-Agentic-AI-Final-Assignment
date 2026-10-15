# Grouping score provenance — 15 October 2026

## Finding

The two 40-case scores belong to different prediction artifacts. The public
40% statement corrected in PR #30 refers to the assistant's manual assignments.
A separate archived agent-label audit reports the same exact total.
Its different family total is attached to a separate prediction artifact.
Do not substitute one comparison for the other.

| Comparison | Exact issue agreement | Family agreement | Evidence inspected |
| --- | ---: | ---: | --- |
| Assistant manual assignments against human answers | 16/40 (40%) | 21/40 (52.5%) | [Original score report](issue-grouping-independent40-score.md); matching frozen 40-row prediction CSV digest |
| Archived agent-label audit against the same named human sample | 16/40 (40%) | 22/40 (55%) | Recovered original audit and triage aggregate JSONs; their input digests match the saved 30,403-row agent-label CSV |
| Grouping agents against a separate model verifier | 511/600 (85.2%) | Not reported here | Saved handoff aggregate only; per-case verifier trail remains unavailable |

The first two reports point to the same frozen human-sheet and sample-manifest
digests. No answer file or source-review content was opened in this closeout.
No score was rerun. CSV inspection was limited to prediction-file headers,
row counts, ID uniqueness where applicable, and whole-file hashes; no individual
prediction or source ID was displayed.

## Recovered artifacts

The earlier attribution task checked the integration checkout, where only the
membership and handoff report were present. This task also located the original
canary checkout. The following artifacts there match the already-published hashes:

| Artifact | SHA-256 |
| --- | --- |
| Assistant `issue_grouping_independent40_predictions_v3.csv` (40 rows) | `68e6782c47795394b69f1ea351cd6db6d28300e8cbba4d0d82e0d19a8c5ba7b5` |
| `agent_labels_v1.csv` (30,403 distinct IDs) | `fd2366d020e3e96d03e9e0a2411b32b611d97116f1e5183bb24cdb456fa7a456` |
| `independent_audit_v1.json` | `48b8acd819774a6493185d5a47e427c244cc933f7040e5d8dab58c463028169c` |
| `blind_diagnostic_v1.json` | `e95fcf6a01e2b7d7608c8cbcc74a64b232d9433019aee490c4808bfe928907c9` |
| `report_v1.json` | `82db52159d1b44108e457fe8bb88acd697b7216025517730561d9e90daac1f60` |

The audit records 16 agreements, 40 cases, and five uncertainty notes. The triage
records 16 exact and 22 family agreements. Both name the agent-label digest above.
The [audit code](../tools/validate_claude_issue_map.py) selects that CSV, and the
[triage code](../tools/diagnose_issue_map_blockers.py) compares its `agent_issue_id`
field. Neither reads the assistant's manual prediction file. The scoring code
was inspected but was not executed on human answers in this task.

This closes the missing-file and score-origin question. It does not independently
recompute the archived agreement or prove how the predictions were generated.

## Claims that must remain withdrawn

Do not call either result “production model accuracy,” a population accuracy
estimate, calibrated confidence, or proof of a correct product priority.

- The assistant manual comparison was not a production grouping-model run.
  Aggregate human family counts were visible before its prediction freeze.
- The archived agent-label score lacks a recovered provider/input/freeze trail
  sufficient to attest blind generation. A matching file hash proves identity,
  not execution, independence, or correctness.
- The 40-case design used five cases per saved topic, not population proportions.
  Five answers carry uncertainty notes. Those human decisions later became
  overrides, so the cases are not untouched holdouts for final membership.
- The 600-case figure measures model-to-model agreement. Its missing case-level
  trail cannot be recreated from aggregate counts.

Keep the corrected live assistant attribution. Preserve the older numeric
reports as dated artifact-level diagnostics with these limits. No labels,
membership, scores, catalog, or release files were changed.
