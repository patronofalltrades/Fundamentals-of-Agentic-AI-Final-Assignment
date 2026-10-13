# Offline issue grouping v4 handoff

This report began in an isolated copy of the canary checkout and is now in the
separate `feat/grouping-v4-integration` worktree. The shared canary and dashboard
checkouts were not edited. No paid call, new inference, push, merge, deployment,
or publication occurred in this continuation.

## Input and corrections

Claude's frozen v1 membership file has SHA-256
`bbc0c84ce046d82215744838107d4e699c0399d0dbcad6a644ece8138233098f`.
It has exactly 30,403 distinct source IDs, one approved issue each. All IDs
match the original complaint/cancellation frame. Recomputed baseline and public
rankings match the supplied v1 CSVs in issue order, counts, and scores. The
source report records 30,403 agent labels, zero missing or invalid issue IDs,
and 9,450 low-confidence labels.

The seven validated human corrections remain separate from saved model output.
Cases 18, 80, and 97 leave the complaint/cancellation frame. The corrected
frame has **30,400 baseline candidates**, including **23 known flagged**,
leaving **30,377 public candidates**. The four other corrections remain
within the frame. All 53 pilot review decisions are recorded in the v4 overlay.
The approved 41-issue catalog is frozen without adding an app-install issue.

| Artifact | SHA-256 |
| --- | --- |
| `docs/issue-catalog-v1.json` | `8c73e62059e86aea48b94da0d4b0bf86df048e0d83442e1ce4bf7b44dc105111` |
| `local/issue_grouping_corrections_v4.json` | `0411331243627624e46c1bc78decd3613fe348a64290171a7a1b5bae810bafa5` |
| `local/issue_grouping_pilot100_v4_overlay.json` | `7f3d88ae8a77474ae74f42760d4403f3cc0a49082f8fc542071e8936ca388fc9` |
| `local/accepted100k_issue_grouping_frame_v4.json` | `afa34a49dca3e80188d85bdb86607d234b628275b62ed2be6b8a9d60e0865787` |
| `local/issue_membership_v4.csv` | `e7ce3bc5f1349c24c7e086843e49a162406b92d30f2ce5e7d915c984929a60fe` |
| `local/issue_ranking_v4.json` | `87c67b07f6ac9d7abdbfa2b36f506dba44c1dec2223e29e9d7367b045582575f` |
| `local/grading_v4_final/manifest.json` | `a589d0a94c24b2e77e94885347342ca54a70a007d4775e3cd29ccd85446a2b8b` |

All private v4 files and grading files are mode 0600 under `local/`.

## Ranking change

The corrected baseline ranks 30,400 members. `GEN-GENERAL` loses two records
and two severity points; `CAT-LYRICS` loses one record and three severity
points. The public projection ranks 30,377 members, excluding 23 known flagged
candidates. It loses one record and one point in `GEN-GENERAL`, and one record
and three points in `CAT-LYRICS`. No issue changes rank. The top baseline issue
remains `USE-ADS`: 5,197 mapped records and severity sum 11,874.

## Evidence limits

The map is model-derived with 51 pilot and 40 blind human overrides. Before
those overrides, the grouping agents agreed with a separate model verifier on
511/600 (85.2%), with the reviewed human pilot on 39/51 (76.5%), and with the
blind human review on 16/40 (40.0%). Those human cases are no longer untouched
holdouts for final membership. The 40% human agreement sharply limits any
claim of semantic accuracy. The memo recommends targeted validation of the
leading issue before a product decision.

The source handoff reports catalog gaps in free-tier limits, blank saved
collections, playback controls, unwanted autoplay, unexpected playlist
additions, ads reported by premium users, app installation, regional
availability, battery/data use, removed features, and lossless audio. Any
catalog change after the approved freeze needs a new approval. The source
handoff reports that 1,500 records were labelled before its personal-information
redaction step was added. The source providers' per-call usage is unavailable;
the private usage log records null calls, tokens, and cost rather than estimates.

## Private export and checks

`local/grading_v4_final/` contains `run.json`, 110,000 selected records in
`records.jsonl.gz` (100,229 structurally accepted and 9,771 nonaccepted),
30,400 memberships, separate baseline and public ranking CSVs, 164 claims,
`memo.md`, claim check, usage log, and a hash manifest. `run.json` sets
`allow_multi_issue` to false and declares all seven human label corrections.
The memo includes no review IDs or review excerpts. The folder is a private
submission handoff, not a public database export.

The dashboard's accepted-evidence importer loaded this folder into an isolated
copy of the local 100k database. It independently reported 41 issues, 30,400
memberships, seven corrections, 164 claims, baseline/public denominators of
30,400/30,377, matching ranking, and `memo_claim_check=passed`. The three new
synthetic ranking tests passed, as did the 13 targeted grouping tests. The
integration worktree then passed all 315 offline Python tests.

In the integration worktree, an independent code-local replay of the frozen
30,403-row membership produced the same corrected 30,400-row membership SHA-256
`e7ce3bc5f1349c24c7e086843e49a162406b92d30f2ce5e7d915c984929a60fe`.
Ranking replay produced the same v4 SHA-256
`87c67b07f6ac9d7abdbfa2b36f506dba44c1dec2223e29e9d7367b045582575f`.
Re-export from the copied private handoff produced the exact original grading
manifest SHA-256
`a589d0a94c24b2e77e94885347342ca54a70a007d4775e3cd29ccd85446a2b8b`.
These were offline code checks with no model call or human answer read.

The instructor-confirmed 100,000-accepted-ID target is met by the earlier
extraction. The unchanged course checker still asks for 660,622 final source
records; this 110,000-selected-row export should not be described as passing
that full-corpus checker without scope confirmation. Public excerpts and
source references still require a separate publication review. The production
dashboard database was not changed here.

## Aggregate-only collaborator handoff

The [provisional memo](provisional-product-priority-memo.md) is byte-identical
to the private grading memo (SHA-256
`e839f30aa39adc9db49b688a205bc7fbd7ae468bf711e6640c27658d09bc68d7`).
The numeric claim ledger is consistent with the saved ranking, but that check
does not verify the meaning of individual reviews. A collaborator can use this
report, the memo, and the frozen catalog without opening private review text or
human answer files. No direct Claude message or receipt was available from
this task's tools; file availability alone is not delivery confirmation.
