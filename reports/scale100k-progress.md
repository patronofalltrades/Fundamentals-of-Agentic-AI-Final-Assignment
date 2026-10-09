# 100,000-review scale checkpoint — October 9, 2026

This report records saved provider results and conservative budget exposure.
**Hanif's October 9 target is at least 100,000 accepted evidence rows for
distinct source IDs**, which may require more than 100,000 selected IDs.
Quarantined, uncertain, invalid, empty-text, and synthetic rows do not count.
Semantic review flags remain separate from structural acceptance and exclude
flagged rows from representative examples pending human review. The separate
$5 Jev and $5 OpenRouter caps remain unchanged. This is not human-label accuracy.

## Latest drained aggregate checkpoint

At the latest reviewed pause, 90,000 source IDs were selected: 80,000 in the
scale queue plus the earlier 10,000 checkpoint. Accepted evidence was 87,003
distinct source IDs: 77,437 in the scale queue plus the earlier 9,566, counted
once. The scale queue retained 1,305 quarantined rows and all uncertain source
memberships. A new Jev request returned a URL error with no saved response or
usage; its full $0.002688 reservation remains held. There were no active
reservations or untouched texts in this gate. Cumulative exposure including
all charges and holds was $2.975983458/$5 Jev and $2.325507220/$5 OpenRouter.

One earlier charged 25-review response ended at the 12,288-output-token limit
with `finish_reason=length`. Its saved usage and $0.002206509 charge match.
All 25 rows remain quarantined without a retry. The offline recovery helper
now leaves truncated responses charged and quarantined while validating and
recovering uniquely identified exact-span rows from other saved responses.
The optional source extension is frozen privately, with positions selected
only in later 10,000-ID gates if the accepted target has not been reached.

## Saved results

- The next 90,000 source IDs and source hashes are frozen in a private manifest. The first 10,000 positions are activated in the durable queue.
- Jev labels: 9,952 source IDs. The stage made 7,847 new successful calls and charged $0.334438734. Four Jev HTTP 529 calls remain uncertain with their full $0.002688 reservations held separately. No uncertain text was retried.
- Evidence: two bounded DeepInfra trials made eight requests of 25 reviews each. The first, short-review sample accepted 100/100 direct results. A more varied sample accepted 94/100; six results failed exact-quote validation. Both trials charged $0.003465668 including reasoning tokens, with no new uncertain request. Their combined direct structural acceptance was 194/200. This is not semantic accuracy.
- The 25-review queue configuration was adopted only after checking those eight saved batches and a 95% direct structural acceptance threshold. Strict source ID, quote, entity-span, provider, privacy, token and cost checks remain in place. The final batch has a separate schema and cache identity when it contains fewer than 25 reviews.
- Paid DeepInfra processing resumed after Hanif directly approved transmitting review text and labels through OpenRouter. The saved first-gate state is now 5,945 accepted evidence rows, 76 quarantined, 44 blocked by earlier uncertain exact texts, and four direct uncertain Jev rows. There are 3,899 distinct untouched labeled evidence texts eligible for requests. No evidence request became newly uncertain. The latest dispatcher stopped at its structural quality gate and drained every in-flight request.
- Three charged malformed batches were retained. An offline exact-span pass recovered 24, 15, and 24 uniquely identified rows respectively, without another POST. Missing, repeated, or invalid rows remain quarantined; raw responses and charges remain unchanged.
- A separate tested performance commit adds deterministic largest-fitting-prefix evidence planning up to 25 reviews and stage-local nonblocking provider cooldown. It is integrated locally. It has not yet processed a live request. Its synthetic suite and the complete repository suite passed 258 tests.

## Budget and stop

Cumulative shared exposure includes prior charges and full conservative holds: Jev $0.714117096/$5 and OpenRouter $1.012891198/$5. The activated first-10,000 gate has measured new charges of $0.334438734 for Jev and $0.080459904 for DeepInfra. There are no active reservations. Four Jev HTTP 529 requests remain uncertain with full holds; earlier uncertain evidence texts remain excluded. The code is paused for publication of the tested performance changes before processing the remaining eligible texts. The local Git origin is another local checkout; an external repository URL and target branch have not yet been verified.

The six invalid trial quotes and two weak quote-specificity observations in a 12-case spot check call for continued structural quarantine and semantic review. The 25-review trial does not establish business accuracy or readiness to publish recommendations.
