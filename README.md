# Spotify review insights — final assignment

This project turns saved Spotify Google Play reviews into an evidence-linked product priority assessment. The assignment scope is **at least 100,000 original source reviews**. The selected run accounts for 110,000 original IDs; 100,229 have structurally accepted labels and evidence. Structural acceptance checks identity, format, and source support. It is not a human accuracy score.

**Deadline:** 13 October 2026, 11:59 pm Pacific Time. **Submission:** public GitHub URL through bCourses, pending.

**Public code repository:** [Fundamentals of Agentic AI Final Assignment](https://github.com/patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment). This local integration branch is not published yet.

## Live dashboard

[Open the read-only dashboard](https://hanif-spotify-insights.vercel.app). No login is required. **It currently shows the 5,000-review development checkpoint.** The private 100,000-review release candidate passed local import and public-copy checks, but has not been deployed or verified in production. The backend reads saved results from its database; opening the page does not run a model.

## Current result

| Stage | Verified status |
| --- | --- |
| Source and evidence | 110,000 selected original IDs; 100,229 structurally accepted and 9,771 nonaccepted. The source ID and hash mapping remains private. [Extraction report](reports/accepted-100k-completion.md). |
| Issue catalog and grouping | Frozen 41-issue catalog. Corrected membership has 30,400 distinct complaint/cancellation candidates, one issue each. [Grouping handoff](reports/grouping-v4-handoff.md). |
| Ranking | Deterministic `severity_sum`, descending, then issue ID ascending. The public projection excludes 23 known flagged candidates and ranks 30,377. The top baseline issue is `USE-ADS` with 5,197 mapped records and severity sum 11,874. This ranking is **advisory**. |
| Product memo | [Provisional memo](reports/provisional-product-priority-memo.md) recommends targeted human review of the leading issue before a product change. Its 164 claim references match saved numbers. Numeric consistency does not establish that the map or recommendation is correct. |
| Human quality check | Before human overrides, grouping agreed with the blind human review on **16/40 (40.0%)**. The 40 cases are no longer untouched holdouts in final membership. Separate model-verifier agreement was 511/600 (85.2%); this is not human accuracy. |
| Dashboard release | The combined local backend now serves the claim-checked memo and one clearly provisional `USE-ADS` recommendation. A private imported database and sanitized public copy are ready locally. The public-copy audit compared 144 API routes with zero differences and found no review IDs, source hashes, long quotes, or exact quotes. Publication review and deployment remain pending. |

The memo proposes a cautious next action. The historical reviews do not establish observed churn, revenue, or causal impact.

## Run locally

Use Python 3.9 or newer and the standard library. Run commands from the repository root. The CLI operates offline and requires no credential:

```sh
python3 -m spotify_pipeline --help
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t . -q
```

The offline pipeline commands are `ingest`, `status`, `checkpoint`, and `cost`; see [implementation notes](docs/implementation.md). They accept arbitrary contract-shaped input CSV paths. The selected large run used bounded saved batches and is documented in the [completion report](reports/accepted-100k-completion.md). Saved ranking and claims can be replayed without a model call. The frozen catalog is [issue-catalog-v1.json](docs/issue-catalog-v1.json).

Private results are in ignored, mode-0600 `local/`. The corrected grading folder is `local/grading_v4_final/`: `run.json`, `records.jsonl.gz`, `membership.csv`, `ranking.csv`, `ranking_public.csv`, `claims.csv`, `memo.md`, `claim_check.json`, `grouping_usage.json`, and `manifest.json`. It includes 110,000 selected records and seven declared human label corrections. **Do not publish this folder or the private database.** Public saved-results access for the 100,000-review release still needs final approval and deployment.

The dashboard application is included in this branch. Its read-only HTTP backend queries a saved SQLite or Postgres database. `/api/summary`, `/api/issues`, `/api/claims`, `/api/memo`, `/api/recommendations`, and `/api/reviews` retrieve stored results. From the repository root, `python3 -m dashboard serve --db local/dashboard_public_v4_release.db` serves the prepared local sanitized copy at `http://127.0.0.1:8765`; it makes no model call. See the [dashboard guide](docs/dashboard.md) for private import, public export, API behavior, and web build instructions. The live URL above currently serves the earlier checkpoint.

## Evaluation and limits

The 50 human golden labels remain in an isolated private file. All **50 source-only predictions were frozen before scoring**. The isolated evaluator measured 52% topic agreement, 76% intent agreement, 28% exact topic–intent–severity agreement, **30/50 exact severity agreement**, severity mean absolute error 0.56, and sentiment mean absolute error 0.21. Twelve human cases are marked `needs_review`; eight source texts overlap development data. A private aggregate report records topic support, confusion counts, and severity-error distribution without case-level answers. These diagnostics do not establish population accuracy. Any golden-influenced revision needs a fresh untouched holdout; freezing this file before scoring cannot rule out earlier golden influence. See the [aggregate evaluation and cost handoff](reports/golden-gap-and-checker-2026-10-12.md). The independent grouping verifier is a separate model, and the 40-case blind human comparison remains the strongest grouping warning. No untouched grouping holdout remains after 91 human overrides. The public projection excludes known flagged complaint/cancellation records; 47 flagged accepted records are excluded from examples. Public excerpts are screened to at most 30 words and use opaque references.

The original course checker still describes a larger scope. The original 660,622-row CSV was downloaded in place through macOS iCloud and verified against its pinned SHA-256. The **unchanged checker** ran against its independently generated full-source reference and the private 110,000-selected-row candidate; it returned **`review_required`, not a pass**. It validated 100,229 completed-record schemas, issue membership, baseline ranking, and numeric claims, but reported 550,622 records missing under its unchanged full-corpus denominator. It also flags 7,980 selected nonaccepted states, missing authentic main-run resume checkpoints and run phases, 949 partial/uncertain call outcomes, 94 unavailable usage fields, and missing verifier/group/memo call records. The instructor permits the 100,000-review scope; the discrepancy is disclosed without changing the checker. The private submission candidate includes the exact full-source ingestion profile and 79,797 authentic main-run call records. Grouping provider per-call token and dollar usage remains **unknown**, not zero. The cold/warm end-to-end cost pilot and remaining grading evidence remain submission risks. See the [checker result and limitations](reports/golden-gap-and-checker-2026-10-12.md).

## Data boundary

Keep original review IDs, raw text, source hashes, exact quotes, human answer files, private databases, and unsanitized exports outside Git. Saved public examples use opaque IDs with a private mapping. Nonaccepted states are public only as sanitized aggregates. The frozen issue catalog and human corrections are versioned; changing them requires a new review. No paid call or model run is required to inspect saved outputs.
