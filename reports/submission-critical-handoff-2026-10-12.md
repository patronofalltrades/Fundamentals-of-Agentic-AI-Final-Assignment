# Mission-critical submission handoff — 12 October 2026

This is an index of saved evidence, not a course-checker pass or permission to upload private files. All `local/` files below are Git-ignored and mode 0600. No review text, original IDs, golden answers, credentials, or private source mapping appear here.

## Grading candidate and unchanged course checker

The private candidate is `local/grading_v4_submission_candidate/`. It contains 110,000 selected original IDs, 100,229 structurally completed rows, 1,791 quarantined, and 7,980 other nonaccepted states. Its `calls.jsonl` holds 79,797 genuine main-run call entries. The original full source has 660,622 IDs and SHA-256 `1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6`.

The unchanged checker returned **`review_required`**, not pass. It confirmed 100,229 valid completed records, 4,569 valid direct cache reuses, and no ingestion, completed-schema, membership, ranking, or numeric-claim flags. Its full-source denominator reports 550,622 missing IDs. Other genuine flags include 7,980 selected nonaccepted states, 949 nonbinary saved call outcomes, 79,797 null historical run phases, 94 unavailable usage fields, 20,938 completed rows without a representable direct call or unified direct cache origin, missing historical verifier/group/memo call records, and two absent main-run checkpoints. The split-origin audit confirms saved label and evidence origins; it does not make them checker-compatible unified origins. Historical request tables and resume logs cannot prove per-call initial/resume phase or reconstruct snapshots. Grouping provider per-call usage remains unknown, never zero-filled. See [checker details](golden-gap-and-checker-2026-10-12.md).

## Golden 50 source-only evaluation

All 50 predictions were frozen before the current score. Topic agreement was 26/50 (52%), intent 38/50 (76%), exact topic–intent–severity 14/50 (28%), and severity exact 30/50. Severity MAE was 0.56 and sentiment MAE 0.21. Twelve human answer rows request review; eight exact source texts overlap development data. Older golden influence cannot be excluded. A golden-informed revision needs a fresh untouched holdout. Case-level answers did not enter coding-model context.

## Separate cold/warm 100-review pilot

The owner used the unchanged 100-row sample (SHA-256 `c884ac3b9be5066995d5063f96ad9af6e5e082975788c1684c4f6b6ea661dd0e`) and approved 41-issue catalog (SHA-256 `8c73e62059e86aea48b94da0d4b0bf86df048e0d83442e1ce4bf7b44dc105111`). The pilot made 100 Jev label calls, four DeepInfra evidence batches, one blind-verifier call, six grouping calls, and one memo call: **112 metered calls**, **$0.007410287** recorded charge, all with usage. It accepted 98 of 100 attempted records; two exact-quote failures were quarantined without retry. Cold active stages took 588.435 seconds. First-to-last elapsed was 1,581.190 seconds, including 992.755 seconds of interruptions and approval pauses. Saved warm replay took 0.008029 seconds and recorded zero outbound calls. A later read-only saved-result validation took 0.019757 seconds, with zero new calls. The warm path reads and validates source/configuration hashes, label/evidence cache inputs, exact quotes, grouping coverage, verifier IDs, ranking, and memo claims; it does not regenerate prose or model inference. Its code is `tools/cost100_harness.py`, with seven synthetic focused tests in `tests/test_cost100_harness.py`. See [pilot details](cost100-partial-checkpoint.md).

The [actual offline calculator](../cost/README.actual-pilot.md) uses `tools/cost100_offline_calculator.py` and the saved private calls/rates. [Saved aggregate checks](cost100-offline-checks.json) have SHA-256 `3e30e6d5f37b43ea3809a4feabe12ec6fd752c30a9d3815c4c2e9c2e4ee0d040`: base API charge $0.007410287; doubled API rates $0.014820574; changing projection volume from 100 to 100,000 leaves measured pilot fields unchanged. Full-run projection is unavailable until stage-specific scaling assumptions are supplied. Local compute cost is unknown. The tracked `cost/measurements.json` and `cost/rates.json` remain older null scaffolds, not this actual pilot.

The pilot files were byte-copied into `local/grading_v4_submission_candidate/cost100_pilot_separate/`; hashes match the originals and all copied files are mode 0600. **Those pilot checkpoints are not the missing historical main-run checkpoints.** Do not add pilot calls or records to the main-run `calls.jsonl` or `records.jsonl.gz`.

## Private artifact hashes

| Artifact (relative to repository root) | SHA-256 |
| --- | --- |
| `local/grading_v4_submission_candidate/run.json` | `02a9380e177b8bd7fbd8c1aa6f7b26bad18340ae887574f17f27c1c988fe809e` |
| `local/grading_v4_submission_candidate/records.jsonl.gz` | `7b61ee62fc89cd67c27ebbd1b14ae33ce04dc71e0b248206495ec89bcd218c31` |
| `local/grading_v4_submission_candidate/calls.jsonl` | `179c8b808324cb733cc2b85fb25d504f1472167638f80856161f82174d252661` |
| `local/grading_v4_submission_candidate/ingestion.json` | `2ffad3c66054b55cf026d28ca21fd43ad1bcad7ffb9fb62fcd27117b15803440` |
| `local/grading_v4_submission_candidate/membership.csv` | `e7ce3bc5f1349c24c7e086843e49a162406b92d30f2ce5e7d915c984929a60fe` |
| `local/grading_v4_submission_candidate/ranking.csv` | `09d558262e6ecadaab24b8c745c53e7306663ef1d7866a83cddd00bf32e18f41` |
| `local/grading_v4_submission_candidate/ranking_public.csv` | `38cc0d446a28eb9a8c731df2962062a95991d58316b5f3abf6aae0b5d916ae1e` |
| `local/grading_v4_submission_candidate/claims.csv` | `2b7bee6ae89150b8ff6abe40544f8e10e84713ac8d636176f1b2ad3f37493f8b` |
| `local/grading_v4_submission_candidate/manifest.json` | `0ca45009b7dcbdf04b6b746df0656c1865b9d9d39df23cc36ffbe80c390f2957` |
| `local/grading_checker_20261012/full_reference.json` | `541cbd0630360e132a90a6fff8a47920f051f464e859cc338d67cec646d80422` |
| `local/grading_checker_20261012/full_check_after_ingestion.json` | `cb07e99dca0f043cea70559daa0c25d54240c969a5879b17e0acf70b547e20e4` |
| `local/grading_checker_20261012/split_origin_provenance_audit.jsonl` | `580a0a157b30a132168867047d16a62d7891845cc4d59d7551632087a34a0425` |
| `local/golden_gap_run_20261012/predictions50_frozen.jsonl` | `42bbc688c71648206cde882c7d4eb72f8ecf8c5154298f5520ce645427228d44` |
| `local/golden_gap_run_20261012/evaluation50_aggregate.json` | `04809b23b1cf108899d54896800b84551759a06a97ebdb7ef87c7f85894ce74a` |
| `local/golden_gap_run_20261012/evaluation50_detailed_aggregate.json` | `68a199ce254950ce14981c980faa3d831fa6dd109749a3d721ffdaa113deea58` |
| `local/golden_gap_run_20261012/evaluation50_error_aggregate.json` | `acd1b146f3c05f8d1cfa06229fe59ef4b9d756037abc39d7bb341ceb850ba1b5` |
| `local/grading_v4_submission_candidate/cost100_pilot_separate/checkpoint_before.json` | `8ea678c52303f274486bd6769e524c9b730276084986fe73218cc4c1adee4dd8` |
| `local/grading_v4_submission_candidate/cost100_pilot_separate/checkpoint_after.json` | `d6a784d5aac21445655fc139ad2f6448a131d05d72541fe8e29ccb4c7b7fe2c5` |
| `local/grading_v4_submission_candidate/cost100_pilot_separate/pilot_calls.jsonl` | `cfbfa9edf7f124f82666290db134271a464f3d54c7d39b0b980759a6319a408f` |
| `local/grading_v4_submission_candidate/cost100_pilot_separate/pilot_records.jsonl` | `e119bb1782a8066c090651f25424bbfe3fee40acddc348fd1545a586fd68002c` |
| `local/grading_v4_submission_candidate/cost100_pilot_separate/rates.json` | `a0adefad52dca1d279f392b983df715087d54322371ee89af1c9795d3aced91a` |
| `local/grading_v4_submission_candidate/cost100_pilot_separate/report.json` | `ec22214b3f3df0b1d380a758c1d7f1189bb61e75650c8b49c890bd5357f34454` |
| `local/grading_v4_submission_candidate/cost100_pilot_separate/pilot.db` | `e132ff1360c5337cced0923595d0fda6de34b1db4cc047b176b97efb97a1d7fd` |
| `local/grading_v4_submission_candidate/free_verification_synthetic/private_free_verification_trace.json` | `b7385da77d43a707955811c73444a400a211905552d734de348c6e1e84bb4408` |

The pilot `checkpoint_before.json` records zero completed evidence IDs; `checkpoint_after.json` records 98. The pilot call export marks 100 initial label calls and 12 resumed calls, within the pilot only.

## Safe verification and release limits

The copied private free-verification trace in the table is accompanied by the [boundary report](free-verification-boundaries-2026-10-12.md) and `tests/test_free_verification_evidence.py`. These exercise synthetic identity, exact-span, and public-boundary controls. They do not establish real planted-error replay, semantic accuracy, or model resistance to prompt injection.

The public excerpt screen, opaque references, sanitized nonaccepted aggregates, 47 blocked accepted examples, and 23 flagged public-ranking exclusions need final publication review and a production URL check. The private grading candidate must not be uploaded publicly. The final bCourses submission should cite the public repository, the live URL after verification, this handoff's aggregate facts, and the checker scope discrepancy.
