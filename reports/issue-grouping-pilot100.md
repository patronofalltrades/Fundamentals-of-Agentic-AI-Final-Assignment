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
| `local/issue_grouping_pilot100_priority_decisions.csv` | `c4c70f064fb1053b6df3bd7cb5172e8c1161d6de00805bc113ac4f9b3de28cdd` | Editable 25-row sheet with source/evidence, provisional choice, alternatives, and blank reviewer decision columns |

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
