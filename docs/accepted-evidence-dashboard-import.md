# Dashboard import contract for the accepted-evidence checkpoint

The private, ignored `spotify-accepted100k-dashboard-handoff-v1` JSON is a
local data exchange, not a file to commit or upload. Its verified SHA-256 is
`01d3f466e86f3d6a010f5e9b28b2c1347e683d925228591ff6fa36a2bb75c39c`.
The benchmark exporter and independent validator are
`tools/final_accepted_export.py` and `tools/validate_accepted_export.py`.
Use a separate dashboard worktree and preserve existing dashboard work.

## Top-level structure

- `coverage`: 110,000 selected original IDs, 100,229 accepted records,
  9,771 nonaccepted or pending records, and 47 known semantic exclusions.
- `records`: accepted rows with all six original source fields, original
  source SHA-256, saved Jev labels, exact evidence quote and entities, and
  separate label/evidence configuration, cache, and request provenance.
- `excluded`: every other selected ID and source SHA-256 with a specific
  terminal or pending state and reason. The 6,522 untouched rows must stay
  `eligible_or_awaiting_label`; do not display them as model failures.
- `request_metadata`: saved scale request status, member count, usage,
  reasoning tokens, elapsed time, charge, and generation ID when available.
- `cost_nusd`: measured scale charges and conservative shared exposure,
  including full unresolved holds and separate provider caps.
- `semantic_overlay`: the verified eight-finding pulse plus earlier audit
  flags; findings annotate records and never rewrite saved labels or evidence.

## Import gates

1. Check the private file digest and schema version. Reject duplicates and
   confirm the accepted and excluded sets partition 110,000 distinct IDs.
2. Recheck each original source hash. Recheck exact quote and entity spans
   against the same record source text. Keep source text and raw model outputs
   in a local database; show only bounded, reviewed examples in the UI.
3. Keep `accepted`, `quarantined`, unresolved or blocked, empty, and pending
   states separate. Only the 100,229 accepted rows may enter descriptive
   accepted-row aggregates. Do not silently treat pending or uncertain as zero.
4. Exclude every record with
   `semantic_review.representative_evidence_blocked_by_known_flags=true`
   from representative examples. There are 47 such accepted IDs: 39 earlier
   flags plus eight later pulse findings. This flag is not a human accuracy
   score; unflagged records have not passed human review.
5. Materialize an import manifest with selected and accepted counts, the
   source/export hashes, all state counts, and an import timestamp. Do not
   publish the raw dataset, local paths, or private handoff file. Any public
   evidence excerpt or source ID needs its own reviewed publication gate.

## Approved public presentation boundary

These choices govern a future public dashboard. They do not authorize a
deployment, merge, or upload of the private handoff. The local import may keep
the original ID, source position, full exact evidence, source text, and raw
responses for validation and audit; public API responses must obey the rules
below. The source is the [BwandoWando Spotify Google Store reviews dataset](https://www.kaggle.com/datasets/bwandowando/3-4-million-spotify-google-store-reviews),
version 2 (17 November 2023), listed as CC0: Public Domain in the Kaggle
metadata. This source license does not remove the need to screen personal
information in displayed excerpts.

1. Show at most 30 words of an accepted review's evidence per public excerpt.
   Screen it for personal information before display and clearly mark it as
   shortened when it is not the full exact quote. Keep the unshortened,
   source-exact validated evidence private. Never use a shortened display
   excerpt as the grading-contract `evidence_quote`.
2. Use an opaque public reference for any public record detail or link. Keep
   its mapping to the original ID, source hash, and source position private.
   Do not return the original ID, source position, or a predictable transform
   of either in a public endpoint.
3. Show nonaccepted states only as aggregate counts with sanitized reason
   categories. Do not expose their individual records, source refs, raw
   exceptions, provider messages, or free-form reason strings.
4. Keep all 47 accepted records with known semantic flags in the processing
   total of 100,229. Exclude them from representative examples and public
   issue rankings until reviewed. Disclose the resulting denominator and that
   the remaining records have not been human-validated.
5. Wait for saved issue membership and ranking before publishing this dataset.
   Do not present raw topic counts as validated issue priorities.

The open dashboard import PR #16 on `feat/accepted100k-import` has the
correct private 110,000-row state partition, but its public API still uses
source-position routes, returns full evidence quotes, and returns individual
nonaccepted reasons. Its issue query also lacks the semantic-flag exclusion.
Those paths require changes and tests before publication. The imported
database must remain private. Its Vercel preview check is green; that check
does not validate these public-data gates. The existing production dashboard
still shows the earlier 500-review development data.

## Grouping and ranking handoff

The validated import has 100,229 accepted source IDs, 1,791 quarantined,
1,457 unresolved or blocked, one empty, and 6,522 untouched pending. Exactly
47 accepted IDs have known semantic flags; 100,182 accepted IDs are eligible
for representative examples under the current flag rule. These are structural
and review-overlay counts, not human accuracy measurements.

Among accepted IDs, 28,743 have `complaint` intent and 1,660 have
`cancellation` intent: 30,403 completed complaint/cancellation records.
Twenty-four of these (22 complaints and two cancellations) have known
semantic flags. A public advisory grouping and ranking that excludes them has
30,379 candidate source IDs. Save the exclusion count and rule with its run
configuration. No issue or membership rows exist yet; no issue-level score,
rank, or product recommendation has been measured.

For the public advisory ranking, create a stable issue taxonomy, save each
candidate's source-ID membership in the private database, validate unique
`(issue_id, source_id)` pairs, and calculate each issue's `complaint_count`
and integer `severity_sum` from saved membership. Set `priority_score` to
`severity_sum`; sort descending by that score, then ascending by issue ID.
Save the denominator, run configuration, exact evidence provenance, and
claim-to-membership links so the memo can be checked offline. Public examples
must also satisfy the excerpt and flag gates above. A grouping model, if
used, receives only its authorized bounded inputs; source identity,
membership arithmetic, ranking, and claim checks remain code-owned.

The supplied grading contract requires **every completed complaint or
cancellation** record in its baseline `membership.csv` to belong to at least
one issue. Thus the proposed public exclusion of 24 flagged but completed
records cannot silently replace the contract baseline. Keep a separate
contract-compatible baseline using all 30,403 completed
complaint/cancellation records, or obtain explicit adjudication of flagged
records and account for any status changes before export. Record both
denominators and never present the public advisory ranking as a passing
grading export. The contract also still requires one final record for all
660,622 source IDs, while this checkpoint has 6,522 pending selected rows and
does not cover the full corpus. The instructor's reported 100,000-row minimum
and the supplied full-corpus checker remain unresolved as a grading-scope
question.

### Private grouping artifact and remaining decision

`tools/issue_grouping_handoff.py prepare` verified the frozen accepted export
and wrote the ignored, mode-0600 `local/accepted100k_issue_grouping_frame.json`.
Its SHA-256 is
`e9d5b4c1f82d3498228ad0ef67f452061023c45b81477403cfe9e533827fe1bf`.
It holds exactly 30,403 distinct complaint/cancellation source IDs, their
original hashes, source text, saved exact evidence, severity, provenance, and
semantic-flag status. Twenty-four IDs are flagged. It is a private grouping
input, not a completed issue map and never a public upload.

The same tool's `rank` action requires a versioned private issue catalog
(`spotify-issue-catalog-v1`, with a stable ID, title, and definition for each
issue) and a CSV with exactly `issue_id,review_id` columns and exactly one
valid membership for each of the 30,403 candidates. It rejects missing,
duplicate, foreign, and unknown-issue memberships. Once supplied, it writes
both the 30,403-record contract baseline and the 30,379-record public
projection using integer severity sums, the issue-ID tie break, and
six-decimal half-up means. It records input checksums for replay.

**Smallest unresolved semantic decision:** approve a stable issue catalog and
mapping procedure for these records. The saved eight primary `topic` labels
are broad classes, not named issue clusters, and no grouping implementation
or membership output exists. This handoff does not turn topics into issue IDs
or invent memberships. The source frame is ready for a separately authorized
grouping role or human mapping; deterministic validation and ranking need no
paid calls after that mapping is saved.

A [64-case issue catalog proposal](issue-grouping-proposal.md) and
machine-readable draft are authorized only for a 100-case pilot. The ranker
rejects the draft for full production membership until separately approved.
The [offline pilot report](../reports/issue-grouping-pilot100.md) records
provisional assignments and private review decisions still needed.

### PR #16 public API acceptance tests

The imported SQLite data passed `PRAGMA quick_check`, and its saved partition
is 100,229 accepted, 1,791 quarantined, 1,457 unresolved, one empty, and
6,522 pending. PR #16 is open and its Vercel preview check is green, but the
current `dashboard/server.py` still returns `row_index` and source hashes in
review lists, serves numeric `/api/reviews/{row_index}` details, includes
unshortened `evidence_quote`, exposes individual nonaccepted `reason`, and
ranks membership without filtering known semantic flags. The preview check
does not test the approved public boundary.

Before any public data import or deployment, add API-level tests that:

1. Reject numeric source-position detail routes and confirm all public record
   links use opaque, nonpredictable references with private ID/hash mapping.
   Inspect list, detail, search, and issue-example responses, not only page
   rendering; none may reveal the original ID, source position, or hash.
2. Reject any public excerpt over 30 words, any unscreened personal
   information, and any shortened excerpt lacking a visible shortened marker.
   Confirm the private exact-source quote remains unchanged and validates.
3. Confirm nonaccepted rows are available only as state counts and sanitized
   reason-category counts; individual detail routes and raw exception or
   provider strings must not return them.
4. Confirm all 47 known semantic flags remain in the accepted processing
   count but never enter public examples; the 24 flagged
   complaint/cancellation records do not enter public issue membership or
   ranking. Show the 30,379 public candidate denominator while keeping all
   30,403 in the private baseline membership.
5. Keep issue ranking and recommendations visibly pending until an explicit
   catalog, complete validated membership, and checked claims are saved.
   Recompute `severity_sum` from membership and severity; assert descending
   score with ascending issue-ID ties and no fabricated issues.

The instructor-reported minimum and Hanif's later target are 100,000 accepted
original IDs, reached by this checkpoint. The supplied grading contract still
specifies 660,622 final records. Disclose that difference in submission
materials and confirm grading scope; do not treat it as a reason to discard
the 100,229 accepted-row result.

Issue grouping, independent verification, the product memo, grading export,
and deployment each need their own checked handoff. This document authorizes
none of those external actions.
