# Local dashboard foundation

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
