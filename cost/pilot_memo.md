# DECISION MEMO: Q1 Investment Priority

## Recommendation

**Invest in Usability next quarter.** Usability issues command 14 complaints [C003-complaint_count, C004-complaint_count, C006-complaint_count, C008-complaint_count] with a combined severity sum of 38 [derived from C003-severity_sum, C004-severity_sum, C006-severity_sum, C008-severity_sum], driven by two critical regressions: a recent UI redesign that removed core playback controls (seeking, repeat) and queue/skip limitations that frustrate users trying to control their listening experience. These issues directly threaten retention and free-tier engagement. While billing concerns rank highest in isolation, they reflect user backlash to usability failures—fixing playback control will reduce premium paywall friction.

## Evidence: Top Issues by Area

**Usability (38 severity, 14 complaints):**
- **Queue and Skip Limitations** [C003-severity_sum: 9]: Users cannot skip more than 6 songs or queue specific tracks. One user stated: "I just want to listen to one song but nooo I have to go through A HOLE PLAYLIST AND I CAN ONLY SKIP 6 OF THEM 6!!!" [C003]
- **Major UI Update Removed Features** [C004-severity_sum: 9]: Seeking and repeat functionality vanished. A user reported: "We can't even go back few second to play music? WHAT IN THE WORLD IS THIS UPDATE?" [C004]
- **Ads Interfere with Playback** [C006-severity_sum: 8]: Free users see ads instead of songs. One noted: "always plays adds instead of songs...if want to enjoy music free without adds don't download this app" [C006]
- **Excessive Advertisements** [C008-severity_sum: 7]: Ads are loud and overwhelming [C008]

**Billing/Support (25 severity, 9 complaints):**
- **Premium Paywall for Basic Features** [C001-severity_sum: 20]: Users must pay to select songs or skip. A user complained: "now you can't even pick a certain song without Spotify premium...forcing you to pay premium for basic things like just listening to music" [C001]

**Playback (28 severity, 8 complaints):**
- **Playback and Integration Issues** [C007-severity_sum: 7]: Google Assistant integration broken; music adjustment bugs [C007]

**Access (8 severity, 2 complaints):** Minimal impact.

## Why Not the Other Areas

**Billing/Support** ranks second in severity (25) but is a symptom, not the root cause. Users resent premium paywalls because recent updates broke free-tier usability—they cannot control playback, skip freely, or avoid ad overload. Fixing usability will reduce the perception that Spotify is "forcing" premium adoption.

**Playback** (28 severity) includes integration bugs, but the top usability issues (queue, seeking, repeat) are more acute and affect more users (14 vs. 8 complaints).

**Access** (8 severity) is negligible.

## Risks and Data Caveats

- **Coverage:** Data spans 100 completed records from 49 complaint/cancellation entries; keyword-based grouping may conflate distinct issues (e.g., "ads" vs. "paywall").
- **Verifier Agreement:** Joint topic-intent-severity agreement is 0.85 [verify_agreement]; severity exact match is 0.85, within-1 is 1.0. Severity estimates are reliable; topic boundaries less so.
- **Recency Bias:** The "recent update" appears in multiple complaints (C004, C005), suggesting a single regression event. Prioritize rollback or rapid hotfix before investing in new features.
- **Outside-Question Issues:** 38 severity in "other" (general quality, update regression, lyrics, catalog) fall outside the four investment areas but signal broader user dissatisfaction; address usability to rebuild trust.
