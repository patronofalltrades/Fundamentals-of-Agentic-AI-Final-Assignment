# Local foundation review — October 5, 2026

Reviewer: Sol via ChatGPT. Scope: local branch `feat/offline-foundation` against
`main`; no inference, publication, dataset changes or golden-answer edits.

## Checks and findings

- Read the supplied `GRADING_CONTRACT.md` and `COST_CALCULATOR.md` alongside the
  implementation. The compact six-string row hash and parsed-row digest match
  the course helper. The saved full report was previously compared exactly with
  that helper. This review did not rerun the full 97.4 MB ingestion.
- Reviewed exact-text cache provenance. The stored source fixes ID, text and row
  hash; reuse requires equal text and configuration, identical classification
  fields, a completed direct origin and its request evidence. Cache chains and
  conflicting completed writes fail. Synthetic tests cover these paths.
- Reviewed SQLite batch transactions, restart, checkpoint and re-ingest paths.
  Single-batch writes are atomic. Checkpoints are written by temporary-file
  replace. Database/report publication has a documented crash window across
  its two files. Backup names now use unique suffixes so an old backup is not
  overwritten by a later run.
- Fixed cost replay so positive enrichment calls without all input/cache/output
  token components remain unresolved. An empty usage object no longer produces
  a zero API subtotal for a positive-call run. Admission now blocks unset
  worker, output and fallback caps even when optional call arguments are absent.
  These are offline calculations; no live spend enforcement is claimed.
- Checked the tracked file list: no source CSV, ZIP, local database, credentials
  or human answer file is tracked. The source golden template is unchanged. Its
  isolated blank working copy is outside the repository. No classifier outputs,
  calls, evaluated labels or paid costs are claimed.
- Updated the collaboration diagram: Alfred is OpenAI Dots; Sol is ChatGPT.
  The verifier receives original text plus the rubric from preparation before
  comparison, with no classifier-to-verifier label edge. The GitHub Mermaid
  structure has 18 declared nodes, 30 valid edge references and two balanced
  subgraphs. No local Mermaid renderer was available.

## Verification

- `python3 -m unittest discover -s tests -t . -q`: 135 tests, all passed.
- `python3 -m spotify_pipeline cost --measurements cost/measurements.json --rates
  cost/rates.json --scenario cost/scenario.json --out /tmp/spotify-review-cost.json`:
  status `not_measured`, `approved_to_scale: false`.
- `git diff --check`: passed.
- Source and golden files: no write. No OpenRouter or runtime-model inference.

The earlier `reports/offline-verification.json` is the pre-review snapshot of
134 tests. This review records the later 135-test result here.

## Remaining work

Integration and publication await coordinating review. The classifier and
verifier runtime routes, actual paid pilot, human golden 50 answers, full
projections, live budget ledger/retries, grouping, ranking, memo and grading
exports remain pending. The calculator is a scaffold, not the required measured
100-review deliverable. Mermaid rendering and a clean-environment setup were
not verified in this review.
