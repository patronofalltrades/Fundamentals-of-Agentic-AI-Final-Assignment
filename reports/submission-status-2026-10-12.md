# Submission and release checkpoint — 12 October 2026

## Verified locally

- 100,229 structurally accepted distinct source IDs from 110,000 selected; 9,771 selected nonaccepted.
- Frozen 41-issue catalog; 30,400 corrected one-per-review memberships. Public ranking excludes 23 flagged candidates, leaving 30,377.
- Provisional memo and 164 claims reconcile numerically. The pre-override blind human comparison is 16/40 (40.0%); semantic accuracy is not established.
- Isolated pipeline suite: 308 tests passed. Dashboard suite: 251 tests ran with one sandbox-only localhost bind error; that HTTP test passed separately with socket permission. Focused dashboard import/privacy tests: 17 passed.
- A private 100k dashboard database was imported. A sanitized local public copy compared 144 API routes with zero differences and zero detected review IDs, source hashes, exact/long quotes, or unexpected tables. It has 110,000 source rows, 100,229 completed rows, 41 issues, 164 claims, and 47 blocked accepted examples.
- The isolated combined branch passed 386 Python tests with localhost socket access. The web privacy test, Astro typecheck, and static build passed. The combined API still compares 144 private/public routes with zero differences and zero detected leaks; it now returns one explicitly provisional recommendation linked to checked claims. The live site has not switched from 5k.
- The fresh ignored, mode-0600 `local/dashboard_public_v4_release.db` has SHA-256 `93e2bec99d49865dac701429d72cdd7cf3439b7cd624ed75954f525066f188b5`. SQLite `quick_check` returned `ok`. It is a local release candidate, not a production deployment.
- The private `local/grading_v4_submission_candidate/` copies the original v4 export and adds the genuine `reports/ingestion.json` source profile. Its manifest records the file hash and declares that ingestion covers the original source before selection. The original `local/grading_v4_final/` remains byte-for-byte unchanged. The candidate is still incomplete for the prescribed grading layout.

## Release and submission gates

1. Review the public excerpts and opaque reference mapping, then approve publication. The live site still serves the 5,000-review checkpoint. The local 100k public database has not been deployed or checked in production.
2. Review the local advisory presentation and deploy only after approval. The combined local API no longer says the 100,000-row minimum is incomplete; it serves one provisional `USE-ADS` recommendation from the saved claim-checked memo and discloses 16/40 blind human agreement. The live site still serves the 5,000-review checkpoint.
3. Make the required saved outputs inspectable without exposing private source mapping. The local grading folder is private and must not be uploaded directly. The supplied checker still expects the older larger scope and has not been changed. The real source-ingestion report is present; no final-run `calls.jsonl`, `checkpoint_before.json`, or `checkpoint_after.json` was found. Gate-1 resume logs cover only part of execution and cannot be relabelled as final call or checkpoint records.
4. Complete or candidly report missing rubric evidence: full 50-case golden predictions and error analysis (the saved accepted-ID diagnostic has 9 predictions and 41 missing); a measured end-to-end cold/warm 100-review cost pilot (`cost/measurements.json` has `cold` and `warm` as null); exact model usage where available; a reviewed real example and failed/ambiguous trace; planted-error and injection checks; demonstrated restart/resume; and final live URL and public GitHub submission through bCourses. If golden answers influenced revisions, disclose that and use a fresh untouched holdout for final scoring. The assignment has no minimum accuracy threshold, but requires honest error analysis.

Numeric claim checks verify references and arithmetic only. Grouping provider per-call tokens/cost are unavailable, not zero. No paid call, model inference, push, merge, deploy, or upload occurred in this integration checkpoint.

## Existing evidence to cite without new execution

| Requirement | Saved evidence | Limit |
| --- | --- | --- |
| Human scoring | [Offline verification](offline-verification-2026-10-12.md) and [evaluation method](../docs/human_evaluation.md) | Nine accepted golden predictions; no complete 50-case result. |
| Pilot and repair | [500-review readiness](checkpoint-500-readiness.md) and [100-review repair diagnostic](deepinfra-recheck100.md) | Neither is a measured full cold/warm 100-review pipeline run. |
| Recovery | [Scale progress](scale100k-progress.md) and [offline throughput check](scale100k-throughput-offline.md) | Actual resume observations and synthetic safety checks are separate; no final before/after checkpoint export. |
| Costs | [Cost scaffold](cost-scaffold.json) and `cost/measurements.json` | Cold and warm measurements remain null; grouping per-call usage is unavailable. |

No complete reviewed source trace, failed or ambiguous case trace, or named planted-error/injection result was located in this branch. A private review and publication screen are required before putting review excerpts in public documentation.

The [narrow paid evaluation proposal](minimal-paid-gap-proposal.md) costs one
possible first segment from saved reservations. It is not authorization to run
it; the end-to-end cost pilot remains separately uncosted and unapproved.
