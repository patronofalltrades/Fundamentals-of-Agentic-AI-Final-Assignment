# Draft issue grouping proposal for the accepted-evidence checkpoint

**Status: review only.** No issue membership, issue score, or product
recommendation has been generated. The [machine-readable proposed catalog](issue-catalog-draft.json)
is marked `draft_unapproved`; the offline ranker
rejects it until its status and mapping rule are reviewed and approved.
No model call, human golden answer, accepted record, or provider account was
used or changed to prepare this proposal.

## Evidence considered and its limits

The private, validated grouping frame contains 30,403 accepted original IDs
with `complaint` or `cancellation` intent. The draft used a deterministic,
bounded 64-record design sample: five records from each of the eight saved
primary topics, plus eight distinct cancellation cases, eight severity-five
cases, and eight cases with known semantic flags. Selection used SHA-256
ranking of the original ID with a fixed design salt; it was not random in a
statistical sense. The ignored, mode-0600 sample is
`local/issue_catalog_review_sample.json`, SHA-256
`7d43c088c0d5f0988b532b82c3630c4fcdcf7213c7ab8259efcee39b4cf4a8a9`.
It contains private source text and IDs and must not be committed or uploaded.

The sample showed distinct problem types inside broad topics: account
sign-in and account-state access; price, charge, and paid entitlement; catalog
availability, recommendations, and lyrics; download versus offline access;
crashes, playback failure, wrong selection, shuffle, and background behavior;
ads, playlist editing, and previews; support response and resolution. Generic
criticism and ambiguous or apparently mismatched saved labels also occurred.
These observations motivate definitions; they are not prevalence estimates,
human accuracy results, or proof that the 37 draft issues cover the corpus.
Some development text can exactly overlap golden-source text under different
IDs. No human answer labels were read, and this sample must not be used to
tune against them.

## Proposed primary-problem mapping rule

1. Read the original review text as data and use the saved exact quote as
   traceable supporting evidence. Saved topic, intent, and severity are cues,
   not issue IDs. Do not infer a specific defect from rating, app version,
   emotion, or a paid-plan mention alone.
2. Assign **one** catalog issue to every completed complaint/cancellation
   original ID. Map cancellation intent to the stated underlying problem; an
   intent to leave is not itself a billing cancellation failure. A departure
   with no stated reason belongs in `GEN-GENERAL`.
3. When several distinct problems are stated, choose the one with the highest
   supported impact under the shared severity rubric. If impact ties or cannot
   be distinguished from saved evidence, use the first specific problem in
   the original text. Record competing issues and uncertainty for review;
   do not silently assign multiple memberships. The draft uses the contract's
   normal one-issue rule, so per-issue counts will not overlap.
4. Apply the catalog's narrow definition before an `*-OTHER` bucket. Use
   `GEN-GENERAL` only for a genuinely nonspecific complaint, never for a
   concrete problem missing from the catalog. A concrete unmatched problem,
   contradictory saved label/evidence, or an unresolvable impact tie goes to
   a private adjudication queue; extend or revise the catalog before final
   membership. Do not invent a supporting quote.
5. For exact-text aliases, reuse a grouping decision only when the original
   text, saved classification, evidence configuration, and approved issue-map
   version match. Still save one membership pair for each original source ID
   and retain direct source provenance.
6. Map the 24 known flagged complaint/cancellation IDs for the private
   contract baseline only after reviewing their source and flag. Keep them
   out of public examples and the public advisory ranking pending resolution.
   The baseline denominator is 30,403; the approved public denominator is
   30,379. Known flags are not a complete quality measure.

### Boundary cases to test

| Reported problem | Proposed route | Boundary |
| --- | --- | --- |
| A charged account still lacks a paid feature | `BIL-ENTITLEMENT` | A mere paid-plan mention with a crash routes to playback. |
| A payment continues after attempted cancellation | `BIL-CANCEL` | A threat to cancel because of ads routes to `USE-ADS`. |
| A selected song is unavailable in the catalog | `CAT-AVAIL` | A different song playing in its place routes to `PLY-SELECTION`. |
| Recommendations are irrelevant or unwanted | `CAT-REC` | Shuffle ignores playlist order routes to `PLY-SHUFFLE`. |
| Downloaded items cannot open without network | `DLD-OFFLINE` | A new download that never completes routes to `DLD-FAIL`. |
| Music stops only after the device locks | `PLY-BACKGROUND` | General buffering or degraded audio routes to `PLY-QUALITY`. |
| Support never answers | `SUP-NOREPLY` | A response that fails to resolve the issue routes to `SUP-UNHELPFUL`. |
| Ads disrupt listening | `USE-ADS` | A subscription price complaint routes to `BIL-PRICE`. |

These are definitions to test, not membership claims about sampled records.

## Small validation pilot before full mapping

Freeze a **new disjoint 100-record** pilot from the private frame: eight per
saved primary topic (64), then 16 additional cancellation records, ten
severity-five records, and ten known-flag records, with exact ID deduplication.
Keep the 64 design-sample IDs out. Have two independent reviewers or a
separately authorized grouping role and reviewer apply the definitions
without seeing each other's decision. Record one proposed issue per ID,
alternative/uncertain issues, whether the exact evidence supports it, and
whether saved labels need adjudication. Do not reveal human golden answers.

Review every disagreement, generic-bucket assignment, flagged case, and
catalog gap. Verify all 100 original IDs and hashes, one membership per ID,
zero foreign or duplicate pairs, stable issue IDs, and a rerun of ranking
from saved membership with no model call. Report agreement and confusion by
issue family, not just a single overall percentage. Revise the draft catalog
and repeat a bounded pilot if definitions are not usable. Only then authorize
the full 30,403-ID mapping. The ranker will calculate the private baseline
and public projection from that saved mapping; it does not make semantic
assignments.

## Decision requested

Approve or edit the 37 stable IDs and definitions in the draft JSON, the
one-primary-problem rule, and the handling of generic and ambiguous cases.
Choose who will make and adjudicate semantic assignments in the pilot. This
review is a semantic gate, not permission to run a paid model or publish data.

The 100,229 accepted-original-ID target is met. The supplied grading contract
still names all 660,622 source IDs while the instructor-reported minimum is
100,000; disclose that difference and verify final grading scope. It does
not block drafting or validating the grouping plan for saved accepted IDs.
