# Offline issue grouping pilot: provisional, not human verified

Hanif authorized a 100-review pilot using the 37-ID draft catalog and
one-primary-problem rule. This was an offline model-assisted reading of saved
development review text and exact evidence. No paid provider call, human
golden-answer access, saved extraction change, full membership map, score,
product recommendation, or publication occurred. The catalog is marked
`pilot_authorized`; the production ranker still rejects it.

## Frozen inputs and private outputs

The pilot was selected deterministically from the validated 30,403-record
complaint/cancellation grouping frame. It has eight distinct exact texts per
saved topic (64), then 16 cancellation, ten severity-five, and ten known-flag
cases. It excludes every design-sample ID **and exact text** and has 100
unique original IDs and 100 unique exact texts. Later strata are deliberately
oversampled; these 100 cases are not a prevalence sample.

All files below are Git-ignored and mode 0600. They contain original IDs or
review text, so they remain private:

| Local artifact | SHA-256 | Contents |
| --- | --- | --- |
| `local/issue_grouping_pilot100_input.json` | `d1501a496f749067f2d4d0885c17219132a8861b989c9cf72c00a487243a2a4c` | Frozen 100 original records, labels, exact evidence, provenance |
| `local/issue_grouping_pilot100_assignments.json` | `812765f07555a7cc4cf3a5092e5bb84d00c0a385a83de521f4ddcbf20ef761fa` | One provisional judgment and evidence rationale per case, with alternatives and ambiguity flags |
| `local/issue_grouping_pilot100_review.json` | `1ac4f88de0e4519a2ac2eccc17b33124c45bd280939c5f3304094fcb72068432` | All 53 cases needing review, source and exact evidence, blank decision fields |
| `local/issue_grouping_pilot100_priority_review.json` | `5e88d03fd76045a65682956284399adcb1797b111c432ef857bec60400e9c154` | Compact first 25 decisions: all ten abstentions, all ten flagged cases, five boundary/label concerns |
| `local/issue_grouping_pilot100_priority_decisions.csv` | `2b7c3de775e127f58851324ecc69c55399d98c20846cab1060914c46439a8230` | Verified current 25-row decision sheet: 22 decisions recorded as confirmed by Hanif on 2026-10-10 (Claude-proposed); cases 29, 92, 97 left blank |

The priority file provides `decision` and `decision_notes` as blank fields.
In the CSV, fill `reviewer_decision`, `chosen_issue_id`, and
`decision_notes` without changing source or provisional columns.
The allowed decisions are `accept_provisional`, `choose_alternative`,
`revise_catalog`, `correct_saved_label`, and `leave_unresolved`. A reviewer
must enter their own decisions; these files are **not** human verification.
The full review file retains every flagged or ambiguous case after the first
25 decisions.

## Observations, not accuracy claims

The offline reviewer proposed a draft issue for **90/100** cases and
abstained on **10/100**. The ten abstentions comprise four app-start/open
failures not clearly represented by the catalog, three device compatibility
or integration cases, one content-policy case, one sleep-timer/data-use case,
and one saved cancellation label that reads as praise. Fifty cases have an
explicit ambiguity note; 32 name at least one alternative issue. All ten
known semantic flags remain in the 53-case review queue. Eleven provisional
assignments use the general-criticism bucket. None of these proportions
estimate whole-dataset frequencies or assignment accuracy.

The pilot exposed additional boundaries to adjudicate: sign-up under the
sign-in issue definition; search versus lyric language; missing library
versus lost offline downloads; recommendations versus added or wrongly played
tracks; application support versus device integration; complaint versus pure
request; and whether a saved exact quote supports the chosen issue when the
full review has several problems. Non-English cases need an independent
translation check. Claims of billing or security harm are user reports, not
independently verified events.

## Gate before broader mapping

Review the 25 priority decisions first, then the remaining 28 flagged or
ambiguous cases. Decide whether the catalog needs explicit app-launch,
device-integration, content-policy, and sleep-timer/data-use issues, or whether
each belongs in a justified existing bucket. Recheck saved intent/quote
alignment where noted. Do not force the abstentions into `GEN-GENERAL`: that
bucket is only for genuinely nonspecific criticism. After catalog revision,
freeze a new mapping-rule version and have an independent reviewer check a
disjoint sample before authorizing all 30,403 memberships. The 24 known
flagged candidates in the full frame remain excluded from the public
30,379-candidate advisory projection pending review; the private baseline
must still account for all 30,403 if completed statuses remain unchanged.

This pilot supports the later 100,000-accepted-ID analysis target. It does
not resolve the supplied full-corpus checker versus instructor-reported
minimum discrepancy, which needs disclosure and scope confirmation.

## Reviewed pilot-only catalog revision, 10 October 2026

Hanif approved adding four draft issues and extending the playback-control
definition. The 25-row decision CSV and this report's prior edited version
were preserved byte-for-byte in ignored mode-0600 snapshots before the
revision. The report's prior CSV digest was stale; the verified CSV digest is
the full value in the table above. The snapshot of the prior report has SHA-256
`5f43c0871b8175d972d3b226124352674277034f0c2da3e79045983f9613c40f`.
No decision field was overwritten.

The versioned catalog now contains **41 pilot issues** under rule
`pilot-primary-problem-v2-20261010`: `APP-LAUNCH` for failure before a usable
screen, `DEV-COMPAT` for the app on the user's own device or OS,
`DEV-INTEGRATION` for an external device/platform connection, and
`GEN-POLICY` for a primary content or platform-policy objection. `PLY-CONTROL`
now explicitly includes a failed sleep timer. The app-launch boundary moves
pilot case 1 from its original `ACC-LOGIN` proposal to a **v2 overlay**
suggestion of `APP-LAUNCH`; the original pilot input and assignments remain
unchanged. The catalog remains `pilot_authorized` with
`production_approved=false`. The production ranker rejects it.

`GEN-POLICY` remains **conditional within the pilot**. An offline lexical
screen of all 30,403 complaint/cancellation records found 69 candidates.
Manual review of those candidates found 27 with a clear policy objection
present, 21 mixed or primary-issue-unclear, and 21 lexical false positives or
another primary problem. Twenty-seven is about 0.09% of the frame; the
screen misses synonyms and other languages, and presence is not verified
primary membership. No threshold for "rare" was agreed, so this diagnostic
supports testing a distinct draft issue but does not approve it for
production ranking. The private diagnostic is
`local/gen_policy_frequency_diagnostic.json`, SHA-256
`ec0e791905fdd19d5414e99cc498a1cab3bc5710b67c3f81b85f158855116a41`.

The private v2 overlay is `local/issue_grouping_pilot100_v2_overlay.json`,
SHA-256 `a2c2a5958b8beeceeb426c25e08cc35664e7038f0a8d31468669259e811c90a9`.
It records all 22 decisions and source/provenance digests: nine catalog
revisions, four label-correction decisions, seven accepted provisional
choices, and two alternatives. Eighteen decisions have pilot issue
suggestions; **none** create production membership. The four label-correction
decisions have no membership, including case 80, whose saved cancellation
intent is disputed and has no chosen issue. Three priority cases (29, 92,
97) remain blank. The case-1 propagation is separate from the 22 decisions.

The other **28** review cases are in ignored private files with original text,
exact evidence, provisional issue and alternatives, and blank human decision
fields: `local/issue_grouping_pilot100_remaining28_v2_review.json` SHA-256
`fa733c40f17ad59c3500b4d04a0159dcaaad141efe6d8c4ffaa60dc8a0af6214`
and editable `local/issue_grouping_pilot100_remaining28_v2_decisions.csv`
SHA-256 `897ebc95fc2913cd704de3a3168c854ecd735d22f3ce46a3cd0ed28f893f540f` (blank original `a0a8633459f0f1c024da6d1350194c25eb3734242b96d3e6c4693c5dfa17c220`
kept as `local/issue_grouping_pilot100_remaining28_v2_decisions.blank_backup.csv`).
On 2026-10-10 Hanif confirmed 25 Claude-proposed decisions in this sheet; cases
22, 31, and 81 remain blank, and cases 43 and 89 add two more label-correction
decisions (six in total) that stay separate from issue assignments.
Case 1 displays the v2 `APP-LAUNCH` suggestion alongside its unchanged v1
proposal. **5 review decisions remain unentered**: two priority blanks
(29, 97) and three of the 28 additional cases (22, 31, 81).
Hanif adopted a freeze/hang rule on 2026-10-10: an app that freezes, hangs, or stops
responding, with no crash and no named playback failure, maps to `PLY-QUALITY`.
It resolves priority case 92 and case 55. The `PLY-QUALITY` catalog wording and the pinned
priority-sheet digest in `tools/reconcile_grouping_pilot_v2.py` (now `a6201fd8ca1f394105b06977635a77b1f40bb80eadb1087bbfbc6543d130b3ae`;
v2-reconciled copy kept as `local/issue_grouping_pilot100_priority_decisions.v2_reconciled_backup.csv`)
were pending at this handoff and are resolved by the v3 catalog and reconciler
below. The six label corrections still require a
separate validated record decision before any full grouping run.

## Pilot v3 reconciliation and blind human-check preparation

The preceding paragraph records the handoff before reconciliation. The
current priority decision CSV hashes to
`a6201fd8ca1f394105b06977635a77b1f40bb80eadb1087bbfbc6543d130b3ae`;
the current remaining-28 CSV hashes to
`897ebc95fc2913cd704de3a3168c854ecd735d22f3ce46a3cd0ed28f893f540f`.
Both were read only. Their earlier byte-exact backups remain ignored and
mode 0600 with SHA-256 values
`2b7c3de775e127f58851324ecc69c55399d98c20846cab1060914c46439a8230`
and `a0a8633459f0f1c024da6d1350194c25eb3734242b96d3e6c4693c5dfa17c220`,
respectively. The user-edited report section above was preserved.
Additional byte-exact snapshots of the current v3 input sheets are
`local/issue_grouping_pilot100_priority_decisions.v3_input_backup.csv` and
`local/issue_grouping_pilot100_remaining28_v3_input_backup.csv`; they have
the same respective SHA-256 values as the current sheets and remain ignored,
mode 0600.

The [pilot-v3 catalog](../docs/issue-catalog-pilot-v3.json) is a new file,
SHA-256 `f612276e5224a260bb4cd866bccab7290c7e9dee938e741017bbf228e3436d7b`.
The v2 catalog remains unchanged. V3 retains 41 issues and
`pilot_authorized` status with `production_approved=false`. It adds the
confirmed freeze/hang rule to `PLY-QUALITY`, includes sign-up failure in
`ACC-LOGIN`, and directs a single named but underspecified product area to
its sole supported issue or the area's `*-OTHER` bucket if several fit.
`GEN-GENERAL` applies only when no product area is named. These are rules for
review, not automatic classifications of the five open cases.

The ignored, mode-0600
`local/issue_grouping_pilot100_v3_overlay.json` (SHA-256
`b0a9e7457f6c202049c39515ac5b62a84e8cccb6a6ebaaf69eafbe95d0a2af83`)
ties both current decision sheets, their backups, the v2 overlay, the new
catalog, and the frozen pilot to exact digests. It records 48 filled decisions:
26 accepted provisional choices, six alternatives, ten catalog revisions,
and six label-correction decisions. Forty-two have pilot issue suggestions;
the six label-correction cases (18, 43, 61, 80, 89, 94) have **no issue
suggestion or membership** pending validated label/quote action. No entry
has production membership. The overlay confirms case 1's APP-LAUNCH pilot
suggestion and PLY-QUALITY for cases 55 and 92. Five human decisions remain
blank: priority cases 29 and 97, and additional cases 22, 31, and 81. Their
blank fields were neither inferred nor filled.

An independent semantic check is prepared but **not performed**. The ignored,
mode-0600 `local/issue_grouping_independent40_blind.csv` (SHA-256
`98f15670d5b4218fa238c251065e7c8a4813c5f79a39f44452498549477d37c9`)
contains 40 new source texts, five per saved topic, with blank issue and
rationale fields and no first issue prediction. Its separate private source
manifest is `local/issue_grouping_independent40_manifest.json` (SHA-256
`65c3d9ad0342099860a1977765fa88c419c17c584464513b0cd8e22d44df0f28`).
Code verified no original ID or exact text overlaps the 64 design or 100
pilot cases. A human must perform the semantic check; structural validation
alone says nothing about grouping accuracy. No review text was sent to a
coding model or external provider in this reconciliation.
