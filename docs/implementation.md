# Offline implementation notes

This package is an offline, Python 3.9+ standard-library-only foundation. It
runs with `python3 -m spotify_pipeline` from the repository root. No
installation, network, model call or provider adapter is required. This is a
local development branch and is not yet published.

Scope is deliberately narrow: source ingestion, bounded-memory dedup and
state, completed/quarantined schema validation, checkpoints and an offline
cost arithmetic scaffold. Separate `tools/` commands validate human labels
and compute aggregate offline agreement against saved records. They do not
generate labels. Provider inference, full projections, live budget
enforcement, grouping, ranking, memo writing and model execution remain
future work.

## Commands

```text
python3 -m spotify_pipeline ingest --input PATH --manifest PATH --db PATH --report PATH
python3 -m spotify_pipeline status --db PATH [--config PATH]
python3 -m spotify_pipeline checkpoint --db PATH --out PATH --config PATH
python3 -m spotify_pipeline cost --measurements PATH --rates PATH --scenario PATH --out PATH
```

All commands are offline. `cost` only replays saved measurements and never
grants approval to scale. There is no paid execution command.

## Contract

Source fields, in order:

```text
review_id, review_text, review_rating, review_likes, app_version, review_timestamp
```

`row_sha256` is the SHA-256 of the compact UTF-8 JSON array of the six exact
original strings: `ensure_ascii=False`, `separators=(",", ":")`,
`sort_keys=True`, `allow_nan=False`. Values are never normalized. The full
file is hashed by streaming its raw bytes.

`parsed_rows_sha256` is the SHA-256 of the concatenated raw bytes of each row
hash, in CSV order.

## Ingestion

- UTF-8-sig, comma CSV with a header of exactly the six source fields. The
  parser uses `csv` strict mode; malformed quoting and invalid UTF-8 become
  validation errors.
- Ratings and likes use full-string matching, so a trailing newline fails.
  Only the canonical timestamp shape `YYYY-MM-DD HH:MM:SS` is accepted.
- Golden files with label columns, reordered headers, malformed row widths,
  blank or duplicate IDs, invalid ratings, likes or timestamps are rejected.
- Empty means `not review_text.strip()`. Empty rows are quarantined as
  `empty_review_text`. A missing app version is counted with
  `not app_version.strip()` and is not quarantined.
- The database is built in an adjacent temporary file. The report is written
  to a temporary file before the database is replaced, so report permission or
  directory errors are caught before publication. A best-effort rollback
  restores the previous database and report if the paired replace fails. This
  is not multi-file atomicity; a crash between the two replaces is a known
  window.
- Input, manifest, database and report paths must be distinct, including
  resolved symlink aliases and SQLite `-journal`/`-wal`/`-shm` sidecars. The
  input and manifest are never overwritten.
- Only a single writer is supported. Close all writers before re-ingesting so
  the atomic replace does not race an open connection.

### Manifest format

The real supplied manifest carries file identity under `files[name]` and the
full-corpus facts at the root:

```json
{
  "files": {"spotify_reviews_18months.csv": {"sha256": "<64 hex>", "bytes": 97400616}},
  "profile": {"records": 660622, "duplicate_review_ids": 0, "empty_review_text": 13, "missing_app_version": 159701},
  "reviews_by_month": {"2022-05": 123},
  "reviews_by_rating": {"1": 1},
  "window": {
    "start_inclusive": "2022-05-17",
    "end_exclusive": "2023-11-17",
    "first_review": "2022-05-17 00:01:07",
    "last_review": "2023-11-15 23:16:10"
  }
}
```

Every file entry must carry both a 64-hex `sha256` and a nonnegative integer
`bytes`. Bare strings and alias keys are rejected so identity cannot be
silently skipped. Only the full corpus name is checked against declared facts.
Declared month and rating distributions must match exactly, so an extra
computed month or rating fails. Declared window bounds are validated
(`start_inclusive` inclusive, `end_exclusive` exclusive) together with exact
first/last timestamps. Samples ignore full root facts and only check identity.

### Report

The report contains the exact contract profile at the top level
(`file_sha256`, `parsed_rows_sha256`, `counts`, `reviews_by_month`,
`reviews_by_rating`, `first_review`, `last_review`) plus an `extended` section
with project facts: distinct nonempty text count, duplicate text excess, byte
size, manifest validation status, preserved-state counts and source-level
status counts. Reports omit absolute paths, original IDs and review texts.
Serialization uses `allow_nan=False`.

## State and schema

SQLite stores exact source fields, the original row hash and order, an
exact-text table with a unique text identity, per-configuration status and
completed classifications with direct cache provenance.

- Exact-text identity uses a unique SQLite text column, so equality is checked
  on the exact string, not inferred from a hash.
- Every original row is counted. Empty rows are quarantined with an explicit
  retrievable reason. Nonempty rows are pending until a configuration
  completes them. Status without a configuration is an unconfigured-source
  count, not a cross-config total.
- Completed records are validated with the stored source as authoritative. A
  caller cannot override `review_id`, `source_sha256`, `review_text` or
  `config_hash`, and quote checks always use the stored text. `label_config`
  must equal the computed configuration hash when supplied, otherwise it is
  derived.
- A completed record needs a nonempty topic, intent, finite sentiment in
  `[-1, 1]`, integer severity in `1..5`, a list of nonblank entities, a
  nonblank exact-source-substring `evidence_quote`, a boolean `needs_review`
  and a nonempty `label_config`. Empty text can never complete.
- A cache key includes the complete model, effort, prompt and schema versions
  plus the exact text. Stars and golden answers are never inputs.
- Cached results must point directly at one currently completed original with
  the exact same text, configuration and classification fields, plus known
  provenance and a nonempty request id. Self references and alias chains are
  rejected. Persisted entities and `needs_review` are normalized before
  comparison.
- Direct results require a nonempty `request_id`, known provenance and no
  `cache_source_id`. Batches are capped at 50, validated all-or-nothing, and
  reject duplicate `(row_index, config)` pairs. Identical repeats are
  idempotent; conflicting writes fail.
- Quarantine never overwrites completed state, requires a valid reason, and
  only accepts `empty_review_text` for empty source text.
- `copy_state_from` streams the old database read-only in bounded chunks after
  validating its source identity and schema version.

## Checkpoints

A checkpoint lists the sorted original `completed_ids` for one configuration
plus the configuration hash and source identity. Pending rows are never
counted as completed. `status` and `checkpoint` open an existing database
read-only and never create a file.

## Cost scaffold

`cost/measurements.json`, `cost/rates.json` and `cost/scenario.json` are
intentionally incomplete. Measurements are `not_measured` with `cold` and
`warm` null. Rates have null prices, a null source and a null date. The budget
ceiling is USD 49.99, strictly under 50, with concurrency 1. The output and
fallback caps are unset (null), so admission is blocked rather than treated as
unbounded. Assumptions are unavailable until measured.

The calculator uses `Decimal` and rejects NaN/Infinity and negative billed
quantities. It validates currency (USD), units, date and a real http(s) rate
source. Billing items are nonoverlapping: `uncached_input_tokens`,
`cached_input_tokens` and `output_tokens` for variable API work, one fixed
call item, and local compute seconds. A legacy total-input field is rejected
as ambiguous. Omitted or null units mean unknown. An explicitly empty object
means no billed items only when no enrichment calls occurred. Positive calls
require all three token-usage components; missing fields stay unresolved.
Missing stage usage, wall time or rates stay
unresolved/null.

Test measurements are labelled `synthetic_fixture` and never claim a genuine
measured pilot. `approved_to_scale` is always false; no human approval is
recorded. Projections are `not_implemented` with null base/conservative
scenarios. Measured replay separates fixed and variable subtotals, but full
projection scaling is not implemented. The admission helper checks
`spent + reserved + next <= budget` with the budget strictly under 50 and
bounded worker/output/fallback parameters; missing caps block admission. This
is offline validation, not proven live spend control.

## Artifacts and ignores

SQLite databases, sidecars, checkpoints and other local state are ignored by
`.gitignore`. Only aggregate reports under `reports/` are tracked. Tests are
synthetic and use temporary directories; they never touch the real dataset.

## Known limitations

- The human answer CSV passed mechanical validation and remains outside Git.
  The evaluator has only synthetic test evidence and no real score because
  runtime predictions do not exist yet.
- The model-input route accepts only six source CSV columns; expected answer
  columns belong solely to the isolated offline evaluator.
- No classification, provider adapter, retry policy or live spend control is
  implemented.
- Full cost projections and fixed-overhead scaling are not implemented.
- Manifest profile comparison covers the declared facts only.
- The database and checkpoints are local ignored artifacts.
- Grouping, ranking, memo and model execution remain planned.
