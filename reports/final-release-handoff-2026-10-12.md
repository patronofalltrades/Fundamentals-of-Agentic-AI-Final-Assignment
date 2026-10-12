# Final release handoff — 12 October 2026

## Published branch and deployment

- Branch: `feat/grouping-v4-integration`.
- Reconciliation commit: `628caefe22852c282492fc0eaa7d8642b45a23f8`.
- README asset commit: `504d064335840118b975d07fafde716b19610e1c`.
- The explicit GitHub feature ref was verified at `504d064`. No remote main merge or course submission occurred.
- Canonical dashboard: <https://hanif-spotify-insights.vercel.app>.
- Production deployment: `dpl_5ZGRgcJrvoaXxQRwzjtmeTQPUkoN`, verified `READY` and promoted.
- Deployed source is an archive of main `00ad910f64f0f8664d42c01740eac9b320ceae5a`, with only `web/src/components/dashboard/evals-section.tsx` replaced by its reviewed version from `628caef`. This one-file difference was checked before upload. No broad feature-branch deployment occurred.
- Canonical HTML serves `/_astro/evals-section.DT9ubAyz.js`. The verified bundle includes the isolated evaluator attribution and the 12-review, eight-overlap, and earlier-influence limits. Chrome rendered the canonical card successfully. These conditional details appear when the matching source-only aggregate is saved.
- Canonical API after promotion: 110,000 selected source rows, 100,229 completed rows, golden status `pending`.

## Golden evaluation: prepared, import blocked

All 50 frozen source-only predictions are complete. Exact agreement is topic 26/50, intent 38/50, severity 30/50, and joint 14/50. Severity MAE is 0.56. The nine-case result is a separate selected-production-run diagnostic.

The adapter rehashed the frozen predictions and the completed human benchmark as opaque file bytes. Both matched their pinned digests. No human answer row was exposed to a model. It saved `local/golden_gap_run_20261012/dashboard_evaluation50.json`, mode 0600, with 50 cases, zero missing predictions, and `official=false`.

No production evaluation write occurred. Existing Vercel access works, but the protected production `DASHBOARD_DATABASE_URL` cannot be retrieved by `vercel env run`. The available integration-managed `DATABASE_URL` points to an older 500-classification database. Its identity does not match the local 100,229-row release, so it was rejected before writing.

Smallest next action: the user can put the existing live `DASHBOARD_DATABASE_URL` in ignored `local/production-import.env` with mode 0600, using a secure local editor or terminal. Do not paste the secret in chat. Then verify release identity, save any previous aggregate, import only `evaluation:original`, and read back the four rates, 50/50 coverage, MAE, and `official=false` through the database and public API. The corrected UI is already deployed.

These scores remain diagnostic. Twelve human rows request review. Eight source texts overlap development data. Earlier golden influence cannot be ruled out. They do not estimate accuracy across all reviews.

## Delivered images

The asset commit changes only these paths:

- `README.md`
- `docs/assets/README.md`
- `docs/assets/agentic-ai-capstone-hero-v2.png`
- `docs/assets/required-outputs.png`
- `docs/assets/production-2026-10-12/MANIFEST.md`
- `docs/assets/production-2026-10-12/overview-review-activity.jpg`
- `docs/assets/production-2026-10-12/issue-ranking-top-five.jpg`
- `docs/assets/production-2026-10-12/evaluation-prompt-benchmark.jpg`

All five image links resolve. Images were visually inspected and hashes checked. The screenshots are dated direct production captures. They contain no review text or original source IDs. Their golden card was pending at capture. The prompt comparison is a separate 100-review rubric comparison. The two generated illustrations are labeled as illustrations, not completion evidence.

## Private interruption/resume video

`synthetic-interruption-resume-demo.mp4` is saved privately in Library and at `local/resume_demo_synthetic_20261013/synthetic-interruption-resume-demo.mp4`. It is 28 seconds, 2560 × 1440, 2,629,620 bytes, mode 0600, and gitignored. SHA-256: `8ab83ff9e875e09b2ae074b749f629bab0fd33f696ef9c906b5b343ff3e3fa8b`.

This new run saved a disk checkpoint after 100 mock label requests, received an actual SIGINT (process exit -2), resumed in a new process, completed 100 synthetic rows with 16 further mock requests, and repeated zero label requests. A third process validated the warm result with zero new requests. Network access was blocked by the driver. The video and its private event log report these actual events. It is an offline synthetic recovery demonstration, not new paid execution or a reconstruction of absent main-run checkpoints. The earlier historical-replay video is superseded.

## Checks and remaining grading limits

- The reconciled implementation passed 408 Python tests, the CLI help check, the default offline cost calculator, and the web privacy test before commit `628caef`.
- Image integration passed link, hash, staged-diff, and whitespace checks.
- The remote Astro/Python deployment build completed successfully. Its dependency audit reported seven high-severity findings; dependency versions were not changed in this narrow release.
- All 11 grading manifest hashes and all 11 checker input hashes matched. The unchanged checker remains `review_required`, with no automatic grade: 110,000 selected versus the unchanged 660,622-source contract, 7,980 nonaccepted selected rows, and historical call/provenance/checkpoint gaps. See `prepublication-reconciliation-2026-10-12.md` for every flag.
- The 100,229 accepted rows satisfy Hanif's accepted-evidence count. This does not clear the unchanged full-source checker. No checker was weakened, missing history invented, or private grading output uploaded.
- No paid model calls, credential changes, billing changes, or cost-file edits were made during this release closeout. Claude's cost changes from main were preserved.
