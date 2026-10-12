# Offline verification checkpoint — October 12, 2026

**Historical checkpoint.** The nine accepted golden predictions below describe
the selected production-run diagnostic at this point in time. A separate
source-only run later froze all 50 predictions and scored them: 26/50 topic,
38/50 intent, 30/50 severity, and 14/50 exact topic–intent–severity. See
[`golden-gap-and-checker-2026-10-12.md`](golden-gap-and-checker-2026-10-12.md).
The remaining gates below are also a snapshot, not the current submission
status.

This checkpoint uses saved outputs only. It makes no model request and does
not approve production grouping, a dashboard import, or a grading claim.

## Saved evidence and accounting

The frozen private export and its four source inputs matched their pinned
SHA-256 digests. The independent validator found 110,000 selected original
IDs, 100,229 structurally accepted rows, 9,771 excluded or pending rows,
6,522 untouched pending rows, and 47 known representative exclusions.
The export SHA-256 remains
`01d3f466e86f3d6a010f5e9b28b2c1347e683d925228591ff6fa36a2bb75c39c`.

Read-only SQLite `quick_check` returned `ok` for the shared budget and both
ten-review canary ledgers. The shared budget has zero active reservations.
Conservative cumulative exposure is $3.310141884 of the $5 Jev cap and
$2.469486956 of the $5 OpenRouter cap, including unresolved holds.

## Human-label diagnostics

The 50-row blank source and completed human answer files matched their
pinned SHA-256 digests. Code selected saved predictions by original ID from
the verified accepted export without reading human answers. The existing
aggregate-only evaluator then scored them. Nine golden source IDs have
accepted predictions; one is pending, one is quarantined, and 39 fall outside
the selected 110,000-ID frame.

| Diagnostic | All nine accepted | Five direct predictions with no development-text overlap |
| --- | ---: | ---: |
| Topic matches | 5 / 9 | 1 / 5 |
| Intent matches | 8 / 9 | 4 / 5 |
| Exact topic, intent, severity matches | 4 / 9 | 0 / 5 |
| Severity mean absolute error | 0.666667 | 1.200000 |
| Sentiment mean absolute error | 0.231667 | 0.143000 |

Four of the nine accepted cases have exact text in the 10,000-review
development sample; all four are saved label and evidence cache aliases.
They account for the four exact triple matches above. The five direct cases
are too few to estimate full-run accuracy, but their topic disagreement is a
quality concern. The evaluator's all-50 agreement denominators count the 41
missing or uncompleted predictions as misses. No golden answer, individual
comparison, source ID, or review text was printed or placed in a model input.
The private prediction and aggregate files remain ignored and owner-readable.

## Grouping check and limits

The [independent 40-case grouping check](issue-grouping-independent40-score.md)
remains at 16/40 exact issue agreement and 21/40 issue-family agreement
against one assistant's frozen assignments. Claude owns the ongoing issue
grouping work. Five pilot decisions and six saved-label corrections remain
open in the current handoff. No approved catalog or complete issue membership
exists here, so the ranker cannot produce a checked 30,403-record baseline or
30,379-record public projection.

## Remaining verification gates

- Obtain complete, independent predictions for all 50 golden source IDs,
  then rerun the isolated evaluator and inspect disagreements privately.
- Complete independent semantic verification, issue membership, deterministic
  ranking, and claim-checked memo work.
- Test the dashboard's public API boundary before data import or deployment.
- Build the course grading export and run its zero-API checker. The supplied
  checker still specifies all 660,622 source IDs; the accepted checkpoint
  covers 110,000 selected IDs, including pending and excluded rows. Confirm
  the instructor's accepted submission scope.

The supplied full-source CSV was locally offloaded by the file provider on
this date. A fresh full-file profile could not run without retrieving it.
Earlier checked ingestion results remain recorded in the repository; this
checkpoint does not claim a new full-source profile or passing grading check.
