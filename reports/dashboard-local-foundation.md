# Dashboard local foundation — October 7, 2026

## Completed locally

- Added a Python standard-library HTTP backend and static dashboard. The API is read-only and binds to loopback by default.
- Added a deterministic SQLite backup import from a complete canonical checkpoint. Reimporting the same source is unchanged; a different source is rejected.
- Added persistent aggregate, analysis-run, issue-membership, and recommendation-link tables in the private database. The issue endpoint computes severity sums from accepted membership and saved labels. No issue mapping or recommendation was generated from the checkpoint.
- Added synthetic tests for import behavior, API delivery, pending states, ranking tie order, and recommendation links.
- Added [start, handoff, and deployment instructions](../docs/dashboard.md).
- Browser QA found that saved review detail was not reachable from review cards and zero-count topics were absent from the filter. Added review drilldown, quote search, and all topic options. The empty message now covers both filters and searches.

## Observed checkpoint

The read-only source checkpoint contained 500 source rows and 500 completed rows. It had 479 distinct nonempty texts. The copied database reports the same counts. A second import returned `unchanged`. Grouping, ranking, recommendations, independent verification, human evaluation, claim checks, and the 100,000-source-row minimum remain pending. The checkpoint's raw topic labels are not validated issue clusters. The source database checksum was identical before and after import.

## Checks

- Full offline Python suite: 186 tests passed, including four new synthetic dashboard tests. The HTTP test used an ephemeral loopback port.
- `python3 -m spotify_pipeline --help` and `python3 -m dashboard --help`: succeeded.
- `node --check dashboard/static/app.js`: succeeded.
- `git diff --check`: succeeded before staging.

## Browser QA follow-up

- Opened the local server at `http://127.0.0.1:8765` in Chrome. Coverage showed 500 source rows, 500 completed rows, and 479 distinct texts. Grouping, ranking, recommendations, verification, and human evaluation showed pending.
- Selected the billing topic. The visible evidence cards changed to billing rows. Searched quotes for `premium`; matching evidence appeared. Opened one saved record and saw its label, severity, sentiment, source row hash, model, prompt, and configuration.
- Selected the zero-count support topic and searched for a nonmatching phrase. The no-results state appeared.
- The desktop layout was inspected visually. A narrow viewport could not be established with the available native browser controls, so responsive visual QA is still unverified. A mobile CSS rule is present but is not proof of a mobile render.
- A screenshot was viewed in the browser QA tool but not saved to Library. The tool did not provide a documented path to export its screenshot bytes as a local file for Library upload. The captured full Chrome window also contained unrelated private browser tabs.

## Integration and deployment gaps

This branch has not been merged, pushed, or deployed. It has no live URL. The canonical `AGENTS.md` and `README.md` were not edited; integrate this code while preserving their updated instructions. Before a public deployment, review evidence quotes for personal details and add access controls, a persistent database volume, and operational limits. A hosting account and any cost need separate selection and approval. The unchanged grading contract still describes full-corpus output; the instructor's reported 100,000-row minimum must be reconciled before claiming checker compliance.
