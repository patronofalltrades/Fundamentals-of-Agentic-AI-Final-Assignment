# Vercel staging plan — code ready, not deployed

The current dashboard is a local `ThreadingHTTPServer` reading an ignored SQLite copy. Do not connect this branch to Vercel as-is. The Vercel Python runtime loads ASGI or WSGI entrypoints as Functions, rather than running a long-lived server process. The local SQLite file is not tracked and must not be bundled. This branch adds `.vercelignore` for CLI upload exclusion and ignores `.vercel/` project-link state. For a Git deployment, inspect tracked files and the build input separately. It does not create a Vercel project, database, credentials, deployment, or URL.

## Status, 7 October 2026

- The Function entry, the Postgres backend and the import contract exist on branch `feat/dashboard-vercel`.
  See [the dashboard guide](dashboard.md).
- Vercel project: `fundamentals-of-agentic-ai-final-assignment` in team `haniframadhan-9680`. It is linked
  to the GitHub repository. The production branch is `main`. Vercel Authentication protects deployment
  URLs except custom domains. The project has no environment variables and no database.
- The public alias returns `404 NOT_FOUND`. `main` has no web output yet.
- A push to any branch makes a preview deployment. A merge to `main` makes a production deployment.

## Staging deployed, 7 October 2026

- **Database:** Neon Postgres, plan `free_v3` (Free), region `iad1`, resource `spotify-dashboard-db`, Neon Auth off.
  It was added through the Vercel Marketplace by `vercel integration add neon`. Its environment variables
  (`DATABASE_URL` and others) are connected to the **preview** and **development** environments only.
  Production has no database yet.
- **Data:** the 500-row `checkpoint_500.csv` bundle (479 distinct texts, `rows_sha256` `814878e9…`).
  The first load took 37 s from Indonesia; the second load returned `unchanged`. Ten API checks gave the same
  JSON from Neon and from the local SQLite copy.
- **Preview:** branch `feat/dashboard-vercel`. Vercel Authentication protects it. An anonymous request gets a
  redirect to the Vercel login. Through `vercel curl`, every route returned 200 in 0.3–0.9 s, and POST
  returned 405.
- **To view:** open the latest preview URL for this branch in the Vercel dashboard while you are logged in to
  team `haniframadhan-9680`.
- **Before submission:** connect the database to production, load the 100,000-row bundle, merge to `main`,
  and make the production URL public for the grader.

## Recommendation

Use one protected Vercel **preview** project for the static dashboard and a read-only Python API. Put saved results in a separate managed Postgres database linked to that project. Neon through Vercel Marketplace is one concrete candidate. Keep offline ingestion, model runs, and analysis imports outside request handlers; they write to the database in controlled batches. Vercel request handlers only read saved rows and aggregates. Keep the existing SQLite app for local development and as the source for a one-time, validated migration.

This is a proposed architecture. No Postgres migration, Function adapter, or Vercel configuration is implemented. The database provider, project, access scope, and cost must be selected before coding the adapter. A SQLite file copied into a Function image or its temporary filesystem would not be the live persistent database for the final 100,000-row result.

## Facts checked October 7, 2026

- [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python) supports ASGI/WSGI entrypoints, defaults to Python 3.12, and bundles files reachable at build time. Its standard Python Function bundle limit is 500 MB uncompressed.
- [Vercel Storage](https://vercel.com/docs/storage) routes relational database needs to Marketplace providers. It names Neon and Supabase and says their limits and plans are provider-specific. Credentials are injected as environment variables after a resource is provisioned.
- [Vercel's Neon listing](https://vercel.com/marketplace/neon) describes managed Postgres and says plans start at $0. It does not establish that this project's data volume and usage fit a free plan. The provider's detailed current price and storage quota were not reliably retrievable in this session.
- [Vercel Hobby](https://vercel.com/docs/plans/hobby) is free for non-commercial personal use. Its included monthly amounts include one million Function invocations, four active CPU hours, and 360 GB-hours of provisioned memory. It lists a five-minute Function maximum and Vercel Authentication for preview and production deployments. The user's actual plan and remaining usage are unknown.
- [Function pricing](https://vercel.com/docs/functions/usage-and-pricing) charges Pro usage by active CPU time, provisioned memory time, and invocations with regional rates. A live bill cannot be estimated without the selected plan, traffic, database, and region. [Function limits](https://vercel.com/docs/functions/limitations) include a 4.5 MB request or response payload limit. The API already pages review results at up to 50 rows.

The 500-row private dashboard copy is about 872 KiB. That is a local observation, not a reliable size forecast for the 100,000-row database. The final database must retain source-row versus distinct-text coverage, original IDs and hashes, classifications and evidence, accepted membership, aggregates, checked claims, and saved recommendations. The browser API should continue withholding original IDs and full review text.

## Staging gate

1. Hanif identifies the Vercel team and existing project, or explicitly approves creating a dedicated project. Confirm its plan, region, remaining usage, preview protection, and who can view it. A Git-connected project may deploy automatically on push; do not connect or push until that behavior is reviewed.
2. Select an existing managed Postgres resource or approve a specific new Neon resource and its plan. Confirm current storage, compute, transfer, connection limits, and any charge or spending ceiling. Do not install an integration, set credentials, or upload rows yet.
3. Decide whether staging may show source-exact evidence quotes. Review them for personal information. Use preview protection and a limited audience; do not assume an unprotected `vercel.app` URL is private.
4. Build a small Postgres schema and one-time importer. Validate source hash, configuration hash, row count, distinct-text count, classification count, direct/cache provenance, and idempotent rerun before switching the API. Keep the import log aggregate-only. No model calls occur during page views or deployment.
5. Add a Vercel-compatible Function entrypoint and a storage adapter; test all API routes against a local Postgres test instance or a selected staging resource. Re-run the offline suite. Check deployed `/api/summary`, review search, evidence drilldown, pending issue/recommendation states, and protected access. Only then add the preview URL to README; add the final live URL after the complete submission is deployed.

The `vercel whoami` read-only check did not establish account access. The CLI's update worker tried to write under the user's Vercel cache and the sandbox denied it. No same-call retry, project link, or deployment was attempted. Current team, project, and billing state are unknown.
