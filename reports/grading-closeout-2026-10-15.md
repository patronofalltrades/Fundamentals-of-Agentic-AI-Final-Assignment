# Grading package closeout — 15 October 2026

## Fresh result

The unchanged course checker was rerun on the existing private candidate and
verified full-source reference, with **no `--gold` input**. It returned
**`review_required`**. Coverage and every issue count match the saved 12 October
result. No ingestion, accepted-record schema, membership, ranking, or numeric
claim flag appeared. The checker calculated 41 ranking rows.

The candidate's 11 manifest-pinned files retained their hashes before and after
the check. All 12 files in the published ZIP match the candidate byte for byte,
including the manifest itself. The ZIP contains `grading/` and those 12 files.
The private checker report is mode 0600 and remains ignored. Only an
[allowlisted aggregate](submission-closeout-checks-2026-10-15.json) is included here.

| Coverage | Count |
| --- | ---: |
| Full-source reference | 660,622 |
| Submitted distinct IDs | 110,000 |
| Valid completed | 100,229 |
| Valid quarantined | 1,791 |
| Invalid or unresolved selected statuses | 7,980 |
| Missing from full reference | 550,622 |
| Valid direct cache reuses | 4,569 |
| Duplicate IDs | 0 |

The live accounting separates 1 empty, 6,522 pending, and 1,457 unresolved,
which total 7,980. No per-row status conversion was performed. Do not silently
convert historical statuses to make the categories agree.

## Disposition of every remaining flag

| Flag | Count | Disposition |
| --- | ---: | --- |
| `missing_records` | 1; 550,622 IDs | Full-corpus scope differs from the selected run. The current assignment also permits at least 100,000 in parts of its text. Preserve both facts and ask the instructor how the unchanged coverage formula applies. |
| `run_manifest_mismatch` | 1 | Declared 110,000 scope differs from the 660,622 reference. Keep the actual scope. |
| `unfinished_classification` | 1 | Actual incomplete selected work. No new execution is authorized. |
| `invalid_status` | 7,980 | Preserve saved pending/unresolved/empty states; no fabricated completion or quarantine. |
| `invalid_call_outcome` | 949 | Saved partial, quarantined-metered, and uncertain outcomes do not fit the binary checker enum. No unsupported outcome conversion. |
| `invalid_run_phase` | 79,797 | Request tables do not preserve reliable initial/resume associations. Time gaps cannot supply them. |
| `invalid_usage` | 94 | Missing usage fields stay null. This represents 47 calls, not 94 separate calls. |
| `unlogged_completed_records` | 1; 20,938 rows | Split/indirect label and evidence origins do not fit one direct call/cache origin. Preserve the authentic separate origins. |
| `missing_model_roles` | 1 | Historical verifier/group/memo call receipts are unavailable. A new replay cannot create those receipts. |
| `resume_call_evidence` | 1 | Historical phase proof is absent. |
| `resume_snapshot_mismatch` | 1 | Authentic main-run checkpoint pair is absent. |
| `unreadable_file` | 2 | The missing main-run before/after checkpoints. Pilot and synthetic checkpoints remain separate. |

Earlier schema/profile/cache adapters are already reflected in the checked
release. A possible one-row adapter would encode the separately reported empty
state as the contract's empty-text quarantine. That needs source-level validation
before any change. Automatic approval review rejected the proposed validation
because it would read private reference review text, even with boolean-only
output. No adapter ran and no status changed. Separate approval for that bounded
code-only check is needed if Hanif wants to pursue it; do not infer its result.

The completed closeout adds reproducible checking and precise aggregate scope
disclosure. It does not claim that a failed grading gate was repaired.
The remaining execution gaps cannot be closed from the inspected evidence. They remain recoverable only if
their owners supply authentic historical artifacts; do not reconstruct them.

All 76,523 Jev calls sent one review each. This satisfies the supplied contract's
maximum of 50, but misses the user's reported instructor request for ten per
request. Concurrent workers do not satisfy that batching request. Historical
evidence batches include 50; the later scale queue uses up to 25.

## Artifact identities and hash conventions

- Release ZIP SHA-256: `a596dae7c47c61b864e03e374e6165b443222fc736e0c741c6e03d5db68d9198`.
- Unchanged checker SHA-256: `d60bd66d84922d934c65b3d42b2c7d36cc738e8c75e2d6f2b2f58bca3141c26d`.
- Full-reference **file bytes** SHA-256: `541cbd0630360e132a90a6fff8a47920f051f464e859cc338d67cec646d80422`.
- Checker's **canonical reference** SHA-256: `bb31d47db9b9a85cd97b3ba6e880915aff41a6127c3accee719c139ab34b7e97`.
- Fresh private report SHA-256: `beb8bf6909b7e797b9e4a519851052fcc91d0b2c38f373a01c8cc689593a446f`.

The raw-file and canonical reference digests are different hash conventions.
An initial preflight compared them incorrectly and stopped before running the
checker. The corrected preflight verified both against their appropriate
identities; it did not alter the reference or checker. Detailed reports contain
case examples and private paths, so their bytes and hashes can differ across
checkouts even when coverage, input identities, and issue counts agree.

## Reproduce without paid calls or golden answers

Download [grading-110k.zip](https://github.com/patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment/releases/download/grading-2026-10-13/grading-110k.zip)
and [SHA256SUMS.txt](https://github.com/patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment/releases/download/grading-2026-10-13/SHA256SUMS.txt).
Place the ZIP at `local/grading-110k.zip`. Set `COURSE_DIR` to the extracted
course dataset directory containing the unchanged checker and source CSV.
Use a new output directory; do not overwrite prior evidence.

```sh
umask 077
python3 -m zipfile -e local/grading-110k.zip local/grading-review
python3 "$COURSE_DIR/check_submission.py" reference --full "$COURSE_DIR/spotify_reviews_18months.csv" --analysis "$COURSE_DIR/spotify_reviews_18months.csv" --out local/grading-review/full-reference.json
python3 "$COURSE_DIR/check_submission.py" check --reference local/grading-review/full-reference.json --submission local/grading-review/grading --out local/grading-review/self-check.json
```

Verify the ZIP hash against the value above before extraction. The source CSV
must match `1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6`.
The checker reads private evidence through local code. Keep the full reference
and detailed report private; inspect only aggregate keys in a model context.
Exit code zero means the report was written. Inspect `status`; it is not a pass.
No `--gold` option is needed for this package check.

The frozen ZIP memo retains its old prose. The corrected current memo is on main
and live; all 164 claim lines remain unchanged. An optional release addendum or
replacement requires separate publication approval and a new recorded checksum.
Do not overwrite the existing release silently.
