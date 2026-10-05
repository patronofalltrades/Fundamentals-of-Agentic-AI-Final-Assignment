# DECISION MEMO: Q1 Investment Priority

## Recommendation

**Invest in Usability next quarter.** Usability issues command 13 complaints with severity_sum 35 [derived from C004, C006, C007, C009], driven by a recent UI redesign that removed core playback controls and excessive ad friction. While Playback (severity_sum 31) and Billing (severity_sum 20) also demand attention, Usability poses the highest immediate churn risk because it affects both free and premium users and stems from a reversible product decision. Restoring the seek-backward control and tuning ad load will recover user trust faster than addressing deeper playback bugs or billing policy friction.

## Evidence: Top Issues by Area

**Usability (5 issues, 13 complaints, severity_sum 35):**
- **UI Update Removes Core Features** (severity_sum 9 [C004-severity_sum]): Users report the redesign eliminated seeking backward and basic playback options. One user stated: "We can't even go back few second to play music? WHAT IN THE WORLD IS THIS UPDATE?" [C004]
- **Ad Overload Impact** (severity_sum 8 [C006-severity_sum]): "Such a worst app ... that always plays adds instead of songs" [C006]
- **Excessive Ad Volume** (severity_sum 7 [C007-severity_sum]): "The ads are so loud" [C007]
- **Forced Shuffle and Skip Limits** (severity_sum 6 [C009-severity_sum]): "I can only skip 6 of them 6!!!" [C009]

**Playback (7 issues, 9 complaints, severity_sum 31):**
- **Playback Feature Issues** (severity_sum 10 [C003-severity_sum]): "I can't play song happly. Can't repeat and play specific part" [C003]

**Billing/Support (3 issues, 7 complaints, severity_sum 20):**
- **Premium Paywall Restrictions** (severity_sum 15 [C002-severity_sum]): "You can't even pick a certain song without Spotify premium" [C002]

## Why Not the Other Areas

**Access** (2 issues, severity_sum 8): Lowest complaint volume and severity; no top-10 issues ranked.

**Playback** (severity_sum 31): Close second, but issues are technical bugs (repeat, Google Assistant integration, audio adjustment) requiring deeper engineering. Usability fixes are faster wins that will reduce churn immediately.

**Billing/Support** (severity_sum 20): Premium paywall tightening is a deliberate monetization strategy. Complaints reflect policy, not product defect. Reversing restrictions risks revenue; addressing Usability does not.

## Risks and Data Caveats

- **Coverage**: 49 complaint/cancellation records analyzed; 100% completion rate. Sample size is modest; patterns may not represent all user segments.
- **Verifier Agreement**: Joint topic-intent-severity agreement is 0.85 [verify_agreement]; severity_exact agreement 0.85. Severity ratings are reliable but not perfect; some issues may be miscategorized.
- **Keyword-Based Grouping**: Issues are derived from keyword clustering. "Ad Overload" and "Excessive Ad Volume" may overlap; consolidation could reveal true magnitude.
- **Recency Bias**: Top issues cluster around the recent update. Longer-term playback bugs may be underrepresented in recent reviews.
