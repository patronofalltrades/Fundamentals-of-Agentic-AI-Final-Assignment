# Final closeout verification — 12 October 2026

This is a read-only check of saved evidence at branch
`feat/grouping-v4-integration`, commit `7062a40`, plus a wording correction to
the historical offline-verification report. No model call, paid call, push,
merge, deployment, public upload, or submission occurred.

## Golden 50

The ignored, mode-0600 frozen prediction file has 50 rows, 50 distinct source
IDs, and 50 `completed` statuses. Its SHA-256 is
`42bbc688c71648206cde882c7d4eb72f8ecf8c5154298f5520ce645427228d44`.
The aggregate and detailed aggregate files match their hashes in the
[submission-critical handoff](submission-critical-handoff-2026-10-12.md). Both
report 50 human rows; the general aggregate reports zero missing predictions.
The detailed aggregate
records 26/50 exact topic, 38/50 exact intent, and 30/50 exact severity. The
general aggregate reports 14/50 exact topic–intent–severity, severity MAE
0.56, and sentiment MAE 0.21. Twelve human rows request review. Case-level
answers were not printed or opened in this check.

The 9/50 figure in the [earlier offline checkpoint](offline-verification-2026-10-12.md)
describes a selected production-run diagnostic before the separate source-only
gap run. It is not the completed golden-50 score. That historical report now
points to the later evaluation without changing its original measurements.
The scored set has development-text overlap and possible earlier golden
influence, so it is not an untouched population-accuracy estimate.

## Grading export and checker

The ignored, mode-0600 candidate has 110,000 record lines with 110,000
distinct source IDs: 100,229 completed, 1,791 quarantined, and 7,980 in other
nonaccepted states. Its main-run call file has 79,797 lines. All 11 files
listed in the candidate manifest match their stored SHA-256 values. All 11
candidate inputs named by the saved checker report also match their recorded
SHA-256 values. The saved full-source checker report matches SHA-256
`cb07e99dca0f043cea70559daa0c25d54240c969a5879b17e0acf70b547e20e4`.

The unchanged checker status is **`review_required`**, with no automatic grade.
It uses 660,622 expected source IDs and reports 550,622 missing under that
full-corpus contract. It confirms 100,229 valid completed records and 4,569
valid direct cache reuses. Other unresolved flags include 7,980 nonaccepted
statuses, 949 nonbinary call outcomes, 79,797 unavailable run phases, 94
unavailable usage fields, 20,938 completed rows without checker-compatible
unified direct origin, and missing authentic main-run checkpoints and
verify/group/memo call records. No saved state was rewritten to suppress a
flag. The reported instructor minimum of 100,000 selected reviews and the
unchanged full-corpus checker are different scopes.

## Checks and safe handoff files

The free Python suite passed **403 tests** with local loopback access.
`python3 -m spotify_pipeline --help` and `git diff --check` passed. The first
sandboxed suite run reached the same 403 tests but its single loopback socket
test was blocked by sandbox permissions; it passed on a permitted rerun.

These tracked text files are the safe closeout handoff:

- `README.md`
- `reports/submission-critical-handoff-2026-10-12.md`
- `reports/golden-gap-and-checker-2026-10-12.md`
- `reports/submission-status-2026-10-12.md`
- `reports/final-closeout-verification-2026-10-12.md`
- `reports/offline-verification-2026-10-12.md` (historical checkpoint)

The `local/` grading candidate, checker output, prediction file, and score
aggregates remain private, Git-ignored, and mode 0600. Do not upload them as
public dashboard or repository files. Hanif reports that the 100k release is
live at <https://hanif-spotify-insights.vercel.app> and that 20 browser checks
passed; this task did not independently rerun those browser checks.
