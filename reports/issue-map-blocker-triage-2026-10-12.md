# Issue-map blockers: offline triage (2026-10-12)

**Attribution review, 15 October:** the historical agent-label scores below
are preserved without rescoring. They claim 22/40 family agreement and must
not be conflated with the assistant manual comparison's 21/40. The latter's
16/40 exact agreement is the source of the corrected public 40% statement.
This review did not read human answers or verify the older scoring inputs.
See [the assistant prediction report](issue-grouping-independent40-score.md)
and [the provenance limitation](evaluation-attribution-and-inclusion-2026-10-15.md).

This is a diagnostic and review queue for the separately preserved
30,403-row original map and 30,400-row corrected membership. It does not
approve the v3 catalog, revise saved labels, or issue a corrected ranking.
The frozen blind answers were read only by
`tools/diagnose_issue_map_blockers.py`; its stdout and private saved result
contain aggregates and hashes, not answer rows or review IDs. The private
aggregate result is `local/claude_issue_map_v1/blind_diagnostic_v1.json`,
SHA-256 `e95fcf6a01e2b7d7608c8cbcc74a64b232d9433019aee490c4808bfe928907c9`.

## What the blind check says

The 40 cases were selected as five per saved topic. This historical triage
reported that pre-override agent labels agreed with human decisions on **16/40 exact issues** and
**22/40 issue families**. Thus 24 exact issue assignments differ, including
18 that cross issue families. Five human answers include uncertainty notes.

| Saved topic | Exact agreement | Family agreement |
| --- | ---: | ---: |
| Access | 2/5 | 2/5 |
| Billing | 3/5 | 3/5 |
| Catalog | 4/5 | 5/5 |
| Downloads | 3/5 | 3/5 |
| Other | 3/5 | 3/5 |
| Playback | 0/5 | 3/5 |
| Support | 1/5 | 2/5 |
| Usability | 0/5 | 1/5 |

High-confidence agent labels agree exactly on **14/28** and low-confidence
labels on **2/12**. These strata are small and the five-per-topic design is
not population representative. Even the high-confidence result does not
support treating that field as a human correctness guarantee. The 18
cross-family misses indicate that catalog wording alone may leave a routing
problem; the current evidence cannot isolate the cause per case without a
separate human adjudication workflow.

In the corrected 30,400-row map, `GEN-GENERAL` holds 3,648 assignments and
the seven `*-OTHER` buckets together hold 1,872. Those are model-assigned
counts, not verified catalog-gap prevalence; some reviews may genuinely be
unspecified or outside the named definitions.

## Catalog decisions to review

These are proposed boundaries for human review, not approved catalog edits.
Each decision needs a documented rule and a focused human-labeled sample
before remapping. The current map must remain frozen as evidence of v1.

| Gap reported in handoff | Decision to make |
| --- | --- |
| Free-tier skip cap, forced shuffle, and inability to pick songs | Decide whether a single free-tier-limits issue should cover plan restrictions, or retain symptom-specific `BIL-PRICE` / `PLY-SELECTION` / `PLY-SHUFFLE` / `PLY-CONTROL` assignments. Distinguish a plan rule from malfunctioning controls. |
| Liked Songs or playlist opens blank | Clarify `ACC-STATE` for account content actually inaccessible or lost versus `USE-PLAYLIST` for a playlist/library screen or navigation failure. |
| Now-playing bar disappears | Clarify `PLY-CONTROL` when controls become unavailable versus `USE-NAV` when only navigation or layout is affected. |
| Unwanted autoplay or start on Bluetooth/car | Decide whether requested-audio control, external-device integration, or unwanted recommendations is primary; the current catalog has no explicit auto-start issue. |
| Songs automatically added to playlists | Clarify `USE-PLAYLIST` versus `CAT-REC`; creation of saved content without consent is different from an unwanted recommendation. |
| Premium users still see ads | Clarify `BIL-ENTITLEMENT` when a paid ad-free benefit is unavailable versus `USE-ADS` for ad frequency during free listening. |
| Install/update failure; regional availability | Decide whether each warrants a named issue. Existing `APP-LAUNCH`, `DEV-COMPAT`, and `CAT-AVAIL` do not clearly cover every case. |
| Battery/data use; removed features; lossless audio | Decide whether these are distinct primary problems or consequences of an existing issue. Do not assign a new issue solely from a keyword. |

## Remaining gates

1. A human catalog owner must settle the boundaries above and explicitly
   approve a versioned catalog. The v3 file remains `pilot_authorized` with
   `production_approved=false`.
2. A human review protocol must adjudicate model-human disagreements and test
   the revised rules on a fresh, disjoint sample. The existing 40 answers are
   a diagnostic set, not a new post-revision validation set. Report exact and
   family agreement by topic and confidence, with uncertainty and sample
   sizes; do not set an accuracy claim from model-model agreement.
3. Cases 18 and 80 have saved-label correction requests, and case 97 has an
   open pilot decision. Their exclusion gives a clean 30,400-row membership
   scope but does not resolve those decisions or change saved source labels.
4. Once a catalog and corrected frame are approved, extend the ranker to
   verify both frozen source hashes and the three-row exclusion manifest,
   then calculate a separately labeled corrected ranking. Existing original
   rankings must not be repurposed.
5. Grouping subscription-agent usage has no per-call log. Record role `group`
   with token and cost fields unavailable. No retrospective number can be
   inferred reliably from the saved CSVs.

No network, paid inference, push, merge, or deployment was used in this triage.
