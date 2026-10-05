# Investment Recommendation: Usability

**Recommendation**

Invest next quarter in **usability**. Reviewers report a derived severity_sum of 38 from [C003-severity_sum] [C004-severity_sum] [C006-severity_sum] [C008-severity_sum] [C011-severity_sum], the highest among the four areas. The top complaint—Premium Paywall for Basic Features—carries severity_sum [C001-severity_sum] and overlaps with usability friction: users cannot skip songs, queue tracks, or seek within songs without premium. A recent UI redesign removed essential player controls [C004-severity_sum], and excessive ads [C008-severity_sum] [C006-severity_sum] make the free experience unusable. Usability is first; playback is second at derived severity_sum 28. The gap is modest (10 points), but usability complaints are more numerous (14 complaints in usability area) and directly addressable through feature restoration and ad-load tuning.

---

## Evidence

**Top issues in usability:**
- Queue and Skip Limitations: severity_sum [C003-severity_sum], 3 complaints [C003-complaint_count]. "I just want to listen to one song but nooo I have to go through A HOLE PLAYLIST AND I CAN ONLY SKIP 6 OF THEM 6!!!" [C003-complaint_count]
- Major UI Update Removed Features: severity_sum [C004-severity_sum], 3 complaints [C004-complaint_count]. "We can't even go back few second to play music? WHAT IN THE WORLD IS THIS UPDATE?" [C004-complaint_count]
- Ads Interfere with Music Playback: severity_sum [C006-severity_sum], 3 complaints [C006-complaint_count]. "Such a worst app ... that always plays adds instead of songs" [C006-complaint_count]
- Excessive and Loud Advertisements: severity_sum [C008-severity_sum], 3 complaints [C008-complaint_count]. "Too many ads.... it's literally useless if u hv not taken premium" [C008-complaint_count]

---

## Why Not the Other Areas

**Playback** (severity_sum 28) ranks second but covers fewer high-severity complaints. The single playback issue in the top 10 is Playback and Integration Issues [C007-severity_sum], affecting only 2 complaints [C007-complaint_count].

**Billing/Support** (severity_sum 25) is driven entirely by the Premium Paywall complaint [C001-severity_sum]. While severe, this issue is partly a usability symptom: users cannot perform basic actions without premium.

**Access** (severity_sum 8) is lowest and does not appear in the top 10 issues.

---

## Risks and Data Caveats

- **Sample size:** 49 complaint or cancellation records across 100 completed reviews; results reflect self-selected app-store feedback, not population behavior.
- **Verifier agreement:** Topic agreement is 1.0 (`verify_agreement.agreement.topic`); severity agreement is 0.85 (`verify_agreement.agreement.severity_exact`), meaning some severity judgments may vary.
- **Keyword-based grouping:** Issues are classifier-labeled; "ads" and "paywall" may conflate distinct user frustrations.
- **Ranking method:** Severity_sum weights complaint frequency by reported intensity; it does not measure implementation scope or business outcomes.
