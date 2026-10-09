# 100,000-review scale checkpoint — October 9, 2026

This report records saved provider results and conservative budget exposure. It does not claim completion of the 100,000-review assignment or human-label accuracy.

## Later checkpoint: 20,000 of the remaining 90,000 activated

After the first gate, the next 10,000 frozen source positions were activated in the same durable queue. The latest offline ledger read has 20,000 selected source IDs, 19,924 saved Jev labels, 16,769 accepted evidence rows, 256 quarantined rows, 71 rows blocked by older uncertain exact texts, 512 newly uncertain direct or alias rows, 2,391 eligible or awaiting-label rows, and one attempted-text alias excluded from dispatch. No request is actively reserved. These categories sum to all 20,000 selected IDs; later gates remain inactive.

Measured charges in the remaining-90,000 queue are $0.658053144 Jev and $0.262171167 DeepInfra, including reasoning usage and charged malformed responses. Cumulative shared exposure, including historical charges and every full uncertain hold, is $1.040419506/$5 Jev and $1.333374941/$5 OpenRouter. These exposure values are not bills. No uncertain text was retried. A saved-response recovery pass after the latest interruption accepted 46 uniquely identified exact-span rows offline, with no POST and no change to charge.

The clean feature branch `feat/scale100k-queue-public` was pushed to the verified project GitHub repository at commit `9446283fa7401eca4398e87264d7ef061cbd2073`. It preserves the dashboard and adds a ledger-persisted eight-request shared default, preventing different runner instances from silently using conflicting worker ceilings. The private runner has the corrected code at local commit `705a100`; 319 integrated and 267 private offline tests passed. It uses four Jev slots by default and at most eight global paid slots. The external feature branch SHA was independently verified.

The command-service transport repeatedly disconnected and killed active paid sessions. An orphaned 25-review DeepInfra reservation had no saved response, usage, or charge; after confirming no runner, it was atomically marked uncertain while retaining its full $0.006938624 hold and source memberships. Later interruptions created additional uncertain calls, whose full holds remain. A detached launch test lacked permission to read this worktree, so it was not used for paid execution. The next segment needs a stable user Terminal session or repaired command transport; the queue is safe to resume only on untouched texts after verifying the process and reservations again.

## Earlier first-gate snapshot

- The next 90,000 source IDs and source hashes are frozen in a private manifest. The first 10,000 positions are activated in the durable queue.
- Jev labels: 9,952 source IDs. The stage made 7,847 new successful calls and charged $0.334438734. Four Jev HTTP 529 calls remain uncertain with their full $0.002688 reservations held separately. No uncertain text was retried.
- Evidence: two bounded DeepInfra trials made eight requests of 25 reviews each. The first, short-review sample accepted 100/100 direct results. A more varied sample accepted 94/100; six results failed exact-quote validation. Both trials charged $0.003465668 including reasoning tokens, with no new uncertain request. Their combined direct structural acceptance was 194/200. This is not semantic accuracy.
- The 25-review queue configuration was adopted only after checking those eight saved batches and a 95% direct structural acceptance threshold. Strict source ID, quote, entity-span, provider, privacy, token and cost checks remain in place. The final batch has a separate schema and cache identity when it contains fewer than 25 reviews.
- Paid DeepInfra processing resumed after Hanif directly approved transmitting review text and labels through OpenRouter. The saved first-gate state is now 5,945 accepted evidence rows, 76 quarantined, 44 blocked by earlier uncertain exact texts, and four direct uncertain Jev rows. There are 3,899 distinct untouched labeled evidence texts eligible for requests. No evidence request became newly uncertain. The latest dispatcher stopped at its structural quality gate and drained every in-flight request.
- Three charged malformed batches were retained. An offline exact-span pass recovered 24, 15, and 24 uniquely identified rows respectively, without another POST. Missing, repeated, or invalid rows remain quarantined; raw responses and charges remain unchanged.
- A tested performance commit added deterministic largest-fitting-prefix evidence planning up to 25 reviews and stage-local nonblocking provider cooldown. Its initial synthetic and complete repository suite passed 258 tests. Later live requests used this code.

## Earlier budget and stop snapshot

At that earlier pause, cumulative shared exposure including prior charges and full conservative holds was Jev $0.714117096/$5 and OpenRouter $1.012891198/$5. The activated first-10,000 gate had measured new charges of $0.334438734 for Jev and $0.080459904 for DeepInfra. There were no active reservations. Four Jev HTTP 529 requests remained uncertain with full holds; earlier uncertain evidence texts remained excluded. See the later checkpoint above for current exposure and publication state.

The six invalid trial quotes and two weak quote-specificity observations in a 12-case spot check call for continued structural quarantine and semantic review. The 25-review trial does not establish business accuracy or readiness to publish recommendations.
