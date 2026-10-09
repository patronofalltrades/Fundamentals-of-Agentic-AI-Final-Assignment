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

Issue grouping, independent verification, the product memo, grading export,
and deployment each need their own checked handoff. This document authorizes
none of those external actions.
