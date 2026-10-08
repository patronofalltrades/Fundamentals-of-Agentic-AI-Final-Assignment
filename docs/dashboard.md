# Dashboard: local foundation and Vercel backend

This branch adds a local, read-only dashboard and API for saved pipeline results. It uses Python 3.9+ and the standard library. Opening the page makes no model call and spends no API credits. This is a development slice, not the final deployed submission.

## Import and start

Run from the dashboard worktree root. The saved 500-row canonical checkpoint in the nearby comparison checkout is at `../../../2026-10-06/task-2/spotify-v2-comparison/local/jev_checkpoint500_complete.db`. The path is local to this workspace; replace it if the worktrees move. The source is opened read-only. The import copies it with SQLite backup into the ignored `local/` folder. It keeps original IDs, source fields and hashes in the database. Repeating the same import reports `unchanged`; a different source cannot overwrite the target.

```sh
python3 -m dashboard import-checkpoint --source ../../../2026-10-06/task-2/spotify-v2-comparison/local/jev_checkpoint500_complete.db --db local/dashboard.db
python3 -m dashboard serve --db local/dashboard.db
```

Open `http://127.0.0.1:8765`. The default bind is local only. The browser sends no credentials. The API rejects POST. The database, raw text and original IDs stay in `local/dashboard.db`; the API shows only row indices, source row hashes, labels and source-exact evidence quotes. Quotes may still contain personal details. Review and redact them before any public deployment.

The saved 500-review Jev v2/Codex checkpoint is a development input. Its observed dashboard coverage is 500 source rows, 500 completed rows, and 479 distinct nonempty texts. This is not 100,000 source reviews. The raw topic counts are classifier outputs, not verified issues or population prevalence.

## API contract

All API routes are GET and return JSON.

| Route | Result |
| --- | --- |
| `/api/summary` | Source identity, source-row and distinct-text coverage, raw label counts, and pending quality/analysis status. |
| `/api/reviews?topic=playback&q=music&limit=20&offset=0` | At most 50 evidence rows per page. `topic` and quote search `q` are optional. |
| `/api/reviews/{row_index}` | One saved label and evidence quote, without the original ID or full text. |
| `/api/issues` | Accepted issue ranking, or an explicit pending state. |
| `/api/issues/{issue_id}` | Ranked issue and up to 20 linked evidence rows. |
| `/api/recommendations` | Saved draft recommendations with supporting issue IDs, or pending. |

The server reads from SQLite for each request. No issue or recommendation is seeded from topic labels. The issue endpoint stays pending until an accepted membership handoff is imported.

## Accepted analysis handoff

After independent grouping has produced accepted issue membership, prepare a JSON file in ignored local state and import it:

```sh
python3 -m dashboard import-analysis --input local/accepted-analysis.json --db local/dashboard.db
```

Shape (values below are placeholders, **not a completed run**):

```json
{
  "run_id": "chosen-run-id",
  "source_sha256": "<the source file hash from /api/summary>",
  "config_hash": "<the config hash from /api/summary>",
  "issues": [
    {"issue_id": "chosen-issue-id", "title": "Human-reviewed issue title", "row_indices": [0]}
  ],
  "recommendations": [
    {"recommendation_id": "draft-id", "text": "Draft recommendation to check", "issue_ids": ["chosen-issue-id"]}
  ]
}
```

The importer checks source and configuration identity. It accepts only completed complaint or cancellation rows as issue members. It rejects repeated members within an issue, unknown issues, and repeated run IDs. The import is one transaction. Runs are immutable. SQL computes `severity_sum` once per review within each issue and sorts by descending score, then ascending issue ID. The database keeps membership and recommendation links. It does not claim verifier agreement or checked memo claims. Saved recommendations show `draft_unverified` until a separate claim-check and human-review workflow exists. Do not import a draft as a final product decision.

The current handoff does not impose a single-issue-per-review rule; one review may support multiple distinct issues. The grouping owner must supply the accepted mapping. The importer does not infer clusters from raw topics. It also does not implement the full grading export or claim table.

## Checks

```sh
python3 -m unittest discover -s tests -t . -v
python3 -m spotify_pipeline --help
python3 -m dashboard --help
node --check dashboard/static/app.js  # optional syntax check when Node is available
```

The dashboard tests use synthetic rows. They cover idempotent import, source mismatch, pending states, membership ranking and tie breaks, recommendation links, HTTP GET, static UI delivery, and read-only POST rejection. They do not measure model quality, live cost, or deployment behavior.

## Deployment work still needed

1. Integrate this branch after reviewing its diff and rerunning tests in the destination branch. Keep the updated canonical `AGENTS.md` and `README.md`; this branch did not edit them.
2. Complete the bounded 10-review batch runtime, durable queue, cache, independent verification, accepted grouping, claim checks, and at least 100,000 source-row run. Retain source-row and distinct-text counts separately. Check the supplied full-corpus grading contract against the instructor's reported 100,000-row minimum.
3. Add deployment packaging, a persistent database volume, access controls, rate limits and a privacy review for evidence quotes. Select a host and approve any account or cost before deployment. Keep the dashboard API read-only for graders.
4. Set the live URL in canonical `README.md` after deployment and verify it loads the saved database without paid reruns. The final deadline is October 13, 2026, 11:59 pm Pacific Time.

No host, account, deployment, or live URL was created in this branch.

## Vercel backend and database (branch `feat/dashboard-vercel`)

The same read-only API now runs in two places:

- **Local:** `python3 -m dashboard serve --db local/dashboard.db` (SQLite, unchanged).
- **Vercel:** `api/index.py` exposes the WSGI app in `dashboard/wsgi.py`. `vercel.json` sends every path to it.

`dashboard/server.py` has one `route()` function. Both entry points call it, so the local and deployed
answers are the same. The deployed Function only reads. It rejects every method except GET and HEAD.
A database error returns `503` with no connection detail.

### Storage backends (`dashboard/backend.py`)

| Variable | Backend | Use |
| --- | --- | --- |
| `DATABASE_URL` (or `POSTGRES_URL`) | Postgres through Neon's HTTPS `/sql` endpoint | Vercel |
| `DASHBOARD_DB` | SQLite file, read-only | Local checks |

The code uses the Python standard library only. It sends Postgres queries over HTTPS, so the Function has
no database driver dependency. **The Neon path has synthetic tests only. It has not run against a live
Neon database yet.**

### Import contract (`dashboard/bundle.py`)

1. Make the private SQLite copy: `python3 -m dashboard import-checkpoint --source <canonical.db> --db local/dashboard.db`.
2. Export a bundle: `python3 -m dashboard export-bundle --db local/dashboard.db --out local/bundle`.
3. Load it: `python3 -m dashboard load-bundle --bundle local/bundle --sqlite local/portable.db`
   or `python3 -m dashboard load-bundle --bundle local/bundle --postgres-env DATABASE_URL`.

The bundle keeps the original `review_id`, `row_sha256`, `text_sha256`, status, labels and the
source-exact evidence quote. It does not keep the full review text, rating, likes, app version or
timestamp. The manifest keeps source rows and distinct texts as separate counts.

The loader is idempotent:

- It checks the `rows.jsonl` hash and every count before a write.
- It refuses a database that holds a different source, configuration or bundle.
- It marks `importing`, inserts rows in chunks with `ON CONFLICT DO NOTHING`, then recounts.
- Only matching counts set `complete`. A stopped load can run again and continue.
- A second load of a complete bundle returns `unchanged`.

**Measured on the real 500-row checkpoint (offline):** the bundle has 500 rows and 479 distinct texts.
`rows.jsonl` is 359,224 bytes. The second load returned `unchanged`. All six API routes returned the
same JSON from the portable database and from the original copy. The source database was not changed.

### UI

- A banner shows demo coverage when the database has fewer than 100,000 source rows.
- Long hashes and quotes wrap. Filters are full width on narrow screens.
- Checked with headless Chrome at 1280 px and inside a true 390 px frame. No sideways scroll at 390 px.

### Checks

`python3 -m unittest discover -s tests -t .` runs 198 tests, including 12 in `tests/test_dashboard_vercel.py`
for the backends, the bundle contract and the WSGI entry.

### Not done (needs approval)

1. Provision the database (proposal: Neon Free through the Vercel Marketplace).
2. Set `DATABASE_URL` in the Vercel project. Load the bundle.
3. Deploy a protected preview from this branch.
4. Port `import-analysis` to the backend interface when accepted issue membership exists.

## Load the pipeline's grading folder (`import-grading`)

The pipeline's grading export (`spotify_pipeline/grading.py`) writes `run.json`, `records.jsonl`,
`membership.csv`, `ranking.csv`, `claims.csv` and `memo.md`. The dashboard loads that folder as it is:

```sh
python3 -m dashboard import-grading --folder <grading-folder> --db local/dashboard.db
python3 -m dashboard import-grading --folder <grading-folder> --postgres-env DATABASE_URL [--issue-names names.json]
```

Before any write, the command checks that:

1. `run.json` names the same source file hash as the dashboard database.
2. Every member review has the same source row hash, intent and severity in `records.jsonl` and in the
   dashboard database. Different values mean a different run.
3. The ranking recomputed from the dashboard's saved labels equals `ranking.csv` in every field.
4. `claims.csv` equals the claims derived from `ranking.csv`.

It then saves the run, issues, membership, claims and memo in one transaction. It compares the API ranking
with `ranking.csv` again after the write. The memo gets `claims_checked` only when it cites every claim ID
with its saved value on the same line. Otherwise the page warns that the memo is not checked.

`--issue-names` is an optional JSON file such as `{"issue-playback": "Playback failures"}`. Without it, the
page shows issue IDs. The command only reads the pipeline's files.

New read-only routes: `/api/claims?issue_id=`, `/api/memo`. `/api/issues/{id}` now includes its claims.

**Compatibility check, 7 October 2026:** a grading folder made by the pipeline's own `export_grading`
(integration branch `fde9262`, synthetic 4-row data) loaded with no error. The ranking matched `ranking.csv`,
and the memo claim check passed.

## Monthly trends, saved evaluations and the top issue

`/api/summary` has three more fields. Each one is `null` or `pending` until its data exists.

### Monthly trends (`trends`)

The month of a review is the first seven characters of `review_timestamp` (`YYYY-MM`). For each month
the dashboard keeps three counts:

- `reviews`: all source rows in that month, completed or not.
- `complaints`: completed rows with intent `complaint` or `cancellation`.
- `severity_sum`: the sum of severity over those complaint and cancellation rows.

The local copy computes the counts from `records.review_timestamp` during `import-checkpoint`.
`export-bundle` writes the counts to `manifest.json` under `months`. It does not add a timestamp to
`rows.jsonl`, so `rows_sha256` does not change. The deployed database keeps only these counts, in
`dashboard_aggregate` as `month_reviews`, `month_complaints` and `month_severity_sum`.

`load-bundle` checks that the month totals equal the row totals. A database that already holds the same
complete bundle, but has no month counts, gets only the month counts. The result is then
`aggregates_refreshed`. The rows are not inserted again. A manifest without `months` still loads.

```json
"trends": {"months": ["2022-05", "2022-06"], "reviews": [2, 1], "complaints": [2, 0],
           "mean_severity": ["3.500000", null]}
```

`mean_severity` is `severity_sum / complaints`, rounded half up to six decimals. It is `null` for a month
with no complaints. `trends` is `null` when the database has no month counts. A local copy made before
this change has none; import it again into a new file to add them.

### Saved evaluation (`import-evaluation`)

The course checker's `score_gold` writes a JSON report with golden-set agreement. Save it with:

```sh
python3 -m dashboard import-evaluation --report <report.json> --label-set original --db local/dashboard.db
python3 -m dashboard import-evaluation --report <report.json> --label-set adjudicated --postgres-env DATABASE_URL
```

The command refuses the report when:

- it has no `label_configs`, or an entry differs from the `label_config` in the dashboard's
  `classifications`. An evaluation of a different classifier must not appear next to these labels;
- an agreement value is not a number from 0 to 1 or `null`;
- `approved_cases` is not an integer of 1 or more.

It saves only summary fields in `dashboard_meta` under `evaluation:<label-set>`. It does not save
per-case results or review IDs. The same report again gives `unchanged`. A different report for the same
label set gives `replaced`. Evaluations are diagnostics, so they can be refreshed.

```json
"evaluation": {"status": "saved", "sets": {"original": {"label_set": "original",
  "benchmark_version": "golden-50-human-v1", "benchmark_sha256": "<64 hex>", "approved_cases": 50,
  "total_cases": 50, "missing_or_invalid_predictions": 0,
  "agreement": {"topic": 0.46, "intent": 0.84, "severity": 0.56, "joint": 0.3},
  "severity_mae_on_valid_predictions": 0.64, "official": true, "label_config": "<label_config>"}}}
```

Without a saved report the field is `{"status": "pending"}`. `quality.human_evaluation` is `saved` when
at least one label set is saved.

### Top issue (`top_issue`)

`top_issue` is rank 1 of `/api/issues`, or `null` when no accepted ranking exists:

```json
"top_issue": {"issue_id": "issue-crash", "title": "Crashes", "mean_severity": "4.500000",
              "priority_score": 9, "complaint_count": 2}
```

Tests: `tests/test_dashboard_trends.py` (synthetic rows only).

**Evaluation reports must name the configuration hash.** In the canonical checkpoint, `classifications.label_config`
holds the configuration hash (for the 500-row checkpoint: `0bda2b8478fab805…`). `import-evaluation` accepts a report
only when its `label_configs` list contains that exact value. A report from a different classifier is refused.

## Evaluations and benchmarks (`/api/evals`)

The page's Evals section shows how the pipeline is tested. Each card states its sample, what it is
compared against, its status (measured, partial, estimate or pending) and its limits.

- `tools/build_eval_registry.py` reads the saved reports in `reports/` and writes `dashboard/evals.json`.
  It copies values only; it records the SHA-256 of each report it read. Run it after a report changes.
  `--check` fails when `dashboard/evals.json` is out of date; a test runs this check.
- The human golden evaluation is not in the registry. The API reads it live from the database after
  `import-evaluation`. The page prefers the `original` human set, because the adjudicated set was
  revised after its author saw model output.
- The integrity checks run on every request: ranking reproduced, memo claims, source fingerprint,
  and no full review texts in the public database.
- When the extractor benchmark is final, save its summary as `reports/extractor-benchmark.json`
  (same item shape as the other entries) and rebuild the registry.
