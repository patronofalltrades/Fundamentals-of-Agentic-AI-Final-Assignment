# Independent issue-map validation (offline, 2026-10-12)

**Recovery update, 15 October:** the original canary audit and agent-label files
have now been located and their published hashes verified. The saved agent-label
aggregate is distinct from the assistant manual comparison. No answers were read
or scores rerun. See [the reconciled provenance](grouping-score-provenance-2026-10-15.md).
The warning below records the earlier integration-checkout inspection.

**Attribution review, 15 October:** the historical production-agent scoring
claim below is preserved as a claim from this audit, not adopted as the source
of the dashboard's 40%. The documented assistant manual comparison is
[16/40 exact and 21/40 family agreement](issue-grouping-independent40-score.md).
The older production-agent triage claims 16/40 exact and 22/40 family agreement.
They name different prediction artifacts. This review did not read human
answers or rerun either score. Keep them separate pending a provenance review;
do not present the assistant's 40% as production grouping accuracy. See the
[attribution audit](evaluation-attribution-and-inclusion-2026-10-15.md).

The private handoff was read first. The original 30,403-row map was hashed and
audited before any correction was derived. The original file remains intact.
`tools/validate_claude_issue_map.py audit` saved the aggregate-only original
audit; `correct` then excluded pilot cases 18, 80, and 97 into a separate
30,400-row membership. `verify` recalculated the original audit and proved the
corrected CSV is exactly the original CSV minus those three source identities.
In this validation, the blind 40 answer file was opened only by the local
`audit` scoring action, which prints and saves aggregates, never answer rows
or private IDs.

## Structural findings

- The original has one valid v3 catalog issue for each of the 30,403 unique
  complaint/cancellation frame IDs. All 30,403 agent labels are present; 9,450
  have low confidence. The final map has 30,312 agent assignments, 51 pilot
  human overrides, and 40 blind-human overrides. The original map matches
  those sources for every row.
- Independent integer severity sums, descending score order with issue-ID tie
  breaking, and six-place half-up means exactly reproduce all 41 rows of both
  saved ranking CSVs. Original baseline denominator: 30,403. Original public
  advisory denominator: 30,379 after 24 known semantic flags.
- Cases 18 and 80 are marked `label_correction_pending` in the frozen v3 pilot
  overlay; case 97 is `human_decision_pending`. Their pilot source digests match
  the frozen grouping frame. Excluding these three leaves 30,400 membership
  rows, 23 known semantic flags, and 30,377 public advisory candidates. This
  is a scope exclusion, not a correction to saved labels, evidence, or the
  accepted export.
- The original ranking CSVs apply only to the original 30,403-row map. No
  corrected ranking was issued. The production ranker currently requires a
  30,403-row frame and an `approved` catalog; the v3 catalog is
  `pilot_authorized` with `production_approved=false`.

## Traceable private artifacts

All private artifacts are ignored by Git and owner-readable under
`local/claude_issue_map_v1/`. The correction manifest records the three pilot
indices and private source identities, both membership digests, the audit
digest, and frozen frame, pilot, and catalog digests.

| Artifact | SHA-256 |
| --- | --- |
| Original membership `issue_membership_v1.csv` | `bbc0c84ce046d82215744838107d4e699c0399d0dbcad6a644ece8138233098f` |
| Independent original audit `independent_audit_v1.json` | `48b8acd819774a6493185d5a47e427c244cc933f7040e5d8dab58c463028169c` |
| Corrected membership `issue_membership_corrected_30400.csv` | `e7ce3bc5f1349c24c7e086843e49a162406b92d30f2ce5e7d915c984929a60fe` |
| Correction manifest `corrected_30400_manifest.json` | `4cd603c5c57d03945433894bc11fa47a5b10da8475541f32ba507eee9b370b14` |
| Frozen grouping frame | `e9d5b4c1f82d3498228ad0ef67f452061023c45b81477403cfe9e533827fe1bf` |
| Pilot v3 catalog | `f612276e5224a260bb4cd866bccab7290c7e9dee938e741017bbf228e3436d7b` |
| Original agent labels | `fd2366d020e3e96d03e9e0a2411b32b611d97116f1e5183bb24cdb456fa7a456` |
| Original baseline ranking | `532187161c785089d1d25de5f0b3e567764ca2e5b7e60a39115098911f8b7040` |
| Original public ranking | `8924af2e666baf4c850c5ccecb437fda63335669caae98e5b18af61b9b293809` |

## Human agreement and claim limits

This historical audit reported that its local scorer reproduced agent agreement with pilot decisions
at **39/51 (76.5%)** and with the blind human set at **16/40 (40.0%)**; five
blind answers carry uncertainty notes. Claude reports blind model-verifier
agreement of 511/600 (85.2%); this validation did not rerun that separate
verifier sample, and it is model-to-model agreement. Neither the historical
40.0% claim nor the separate assistant manual comparison establishes that individual issue assignments are human-validated, that
confidence labels calibrate human correctness, or that the model-derived
ranking is an accurate production priority ordering. Structural completeness
and arithmetic agreement do not establish those claims. The 40-case sample
also cannot estimate every issue's precision reliably.

## Catalog and usage gaps

The handoff reports unresolved catalog boundaries for free-tier limits (skip
cap, forced shuffle, choosing songs); blank Liked Songs or playlists; a missing
now-playing bar; unwanted autoplay or auto-start on Bluetooth and cars; songs
automatically added to playlists; Premium users seeing ads; app install or
update failure; regional availability; battery or data use; removed features;
and lossless audio. These are reported taxonomy gaps, without adjudicated
frequencies. The v3 catalog's approval state remains unchanged.

For the eight subscription grouping agents and one subscription verifier, the
grouping role's per-call input/output tokens, call counts, and cost are
**unavailable**; no API usage log was provided. They must remain unknown, not
zero or estimated. This validation used local files only and made no paid
inference calls.

## Verification

- `python3 -m tools.validate_claude_issue_map audit`: passed before exclusion.
- `python3 -m tools.validate_claude_issue_map correct`: wrote separate artifact.
- `python3 -m tools.validate_claude_issue_map verify`: passed, including exact
  three-row delta, private manifest links, and recomputed original ranks.
- `python3 -m unittest discover -s tests -t . -q`: 310 tests passed.
- `git diff --check`: passed.

No push, merge, or deployment was performed for this validation.
