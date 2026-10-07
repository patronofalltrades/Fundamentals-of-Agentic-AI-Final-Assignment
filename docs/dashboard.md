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
