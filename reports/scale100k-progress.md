# 100,000-review scale checkpoint — October 8, 2026

This report covers the first 10,000 of the approved remaining 90,000 source reviews. It records saved provider results and conservative budget exposure. It does not claim completion of the 100,000-review assignment or human-label accuracy.

## Saved results

- The next 90,000 source IDs and source hashes are frozen in a private manifest. The first 10,000 positions are activated in the durable queue.
- Jev labels: 9,952 source IDs. The stage made 7,847 new successful calls and charged $0.334438734. Four Jev HTTP 529 calls remain uncertain with their full $0.002688 reservations held separately. No uncertain text was retried.
- Evidence: two bounded DeepInfra trials made eight requests of 25 reviews each. The first, short-review sample accepted 100/100 direct results. A more varied sample accepted 94/100; six results failed exact-quote validation. Both trials charged $0.003465668 including reasoning tokens, with no new uncertain request. Their combined direct structural acceptance was 194/200. This is not semantic accuracy.
- The 25-review queue configuration was adopted only after checking those eight saved batches and a 95% direct structural acceptance threshold. Strict source ID, quote, entity-span, provider, privacy, token and cost checks remain in place. The final batch has a separate schema and cache identity when it contains fewer than 25 reviews.
- Current source states within the activated 10,000: 2,076 accepted evidence rows, six directly quarantined, 44 blocked by earlier uncertain exact texts, four direct uncertain Jev rows, and 7,870 awaiting evidence or alias settlement. There are 7,774 distinct untouched labeled evidence texts eligible for requests.

## Budget and stop

Cumulative shared exposure includes prior charges and full conservative holds: Jev $0.714117096/$5 and OpenRouter $0.935896962/$5. The paid evidence continuation was rejected **before process creation** by automatic approval review. Its stated reason was missing explicit user approval to transmit private review text to DeepInfra through OpenRouter, despite approval for the review count and caps. A direct destination-approval request is pending. Read-only verification found zero new request, reservation, or charge after that rejection.

The six invalid trial quotes and two weak quote-specificity observations in a 12-case spot check call for continued structural quarantine and semantic review. The 25-review trial does not establish business accuracy or readiness to publish recommendations.
