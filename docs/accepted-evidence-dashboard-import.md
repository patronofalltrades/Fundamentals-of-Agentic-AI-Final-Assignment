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

The source selection is a development checkpoint, not the full 660,622-ID
corpus required by the unchanged grading contract. Issue grouping, priority
ranking, independent verification, product memo, and deployment each need
their own checked handoff. This document does not authorize a deployment.
