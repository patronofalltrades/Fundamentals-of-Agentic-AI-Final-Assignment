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
| Dashboard release | A private imported database and a sanitized public copy are ready locally. The public-copy audit compared 144 API routes with zero differences and found no review IDs, source hashes, long quotes, or exact quotes. Publication review and deployment remain pending. |

The memo proposes a cautious next action. The historical reviews do not establish observed churn, revenue, or causal impact.

## Run locally

Use Python 3.9 or newer and the standard library. Run commands from the repository root. The CLI operates offline and requires no credential:

```sh
python3 -m spotify_pipeline --help
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -t . -q
```

The offline pipeline commands are `ingest`, `status`, `checkpoint`, and `cost`; see [implementation notes](docs/implementation.md). They accept arbitrary contract-shaped input CSV paths. The selected large run used bounded saved batches and is documented in the [completion report](reports/accepted-100k-completion.md). Saved ranking and claims can be replayed without a model call. The frozen catalog is [issue-catalog-v1.json](docs/issue-catalog-v1.json).

Private results are in ignored, mode-0600 `local/`. The corrected grading folder is `local/grading_v4_final/`: `run.json`, `records.jsonl.gz`, `membership.csv`, `ranking.csv`, `ranking_public.csv`, `claims.csv`, `memo.md`, `claim_check.json`, `grouping_usage.json`, and `manifest.json`. It includes 110,000 selected records and seven declared human label corrections. **Do not publish this folder or the private database.** Public saved-results access for the 100,000-review release still needs final approval and deployment.

The dashboard application uses a read-only HTTP backend over a saved SQLite or Postgres database. Its `/api/summary`, `/api/issues`, `/api/claims`, `/api/memo`, and `/api/reviews` routes retrieve stored results. From the dashboard checkout, `python3 -m dashboard serve --db local/dashboard.db` serves a prepared local copy at `http://127.0.0.1:8765`; the site itself uses its configured saved database. The [dashboard guide](docs/accepted-evidence-dashboard-import.md) describes private import and public export. The live URL above currently serves the earlier checkpoint.

## Evaluation and limits

The 50 human golden labels exist in an isolated private file. Only nine have accepted predictions in the saved checkpoint, so there is no full 50-case accuracy score. The independent grouping verifier is a separate model, and the 40-case blind human comparison is the strongest available grouping warning. No untouched final holdout remains after 91 human overrides. The public projection excludes known flagged complaint/cancellation records; 47 flagged accepted records are excluded from examples. Public excerpts are screened to at most 30 words and use opaque references.

The original course checker still describes a larger scope. This 110,000-selected-row export must not be called a pass of that unchanged checker. The instructor permits the 100,000-review scope; the discrepancy is disclosed without changing the checker. Grouping provider per-call token and dollar usage was not recorded and remains **unknown**, not zero. The cold/warm end-to-end cost pilot, complete golden evaluation, and some prescribed grading files remain submission risks. A private submission candidate now includes the genuine source-ingestion report; call and before/after checkpoint files remain missing. See the [release and submission checklist](reports/submission-status-2026-10-12.md).

## Data boundary

Keep original review IDs, raw text, source hashes, exact quotes, human answer files, private databases, and unsanitized exports outside Git. Saved public examples use opaque IDs with a private mapping. Nonaccepted states are public only as sanitized aggregates. The frozen issue catalog and human corrections are versioned; changing them requires a new review. No paid call or model run is required to inspect saved outputs.
