# Post-mortem: billed DeepInfra response rejected by evidence validation

**Incident date:** October 7, 2026. **Scope:** approved 100-development-review
OpenRouter extractor comparison. **State:** six accepted results from three
reviews on each route; one received DeepInfra response rejected; no new paid
calls during this investigation. The comparison remains incomplete.

**Later control update:** This report explains the first incident. Subsequent
continuations exposed two more DeepInfra row failures and two Groq row
failures, including a provider-side strict-schema rejection. The current
runner skips confirmed metered row-output failures and pauses only a route
with **five consecutive** such failures. For current counts and cap exposure,
see `openrouter-extractor-benchmark.md`.

## What happened

1. The runner reused three accepted DeepInfra results from the earlier smoke
   test. The next DeepInfra request used `openai/gpt-oss-120b`, pinned to
   `deepinfra/bf16`, with strict JSON schema, no fallback, data-collection
   deny, and ZDR requested. The schema requires `entities` (up to ten strings)
   and `evidence_quote` (a string). The prompt asks for exact source spans.
2. OpenRouter received the request and returned generation
   `gen-1791346049-zjFNXPVSGXeCPpv4ydkv`. Its authenticated account log
   shows DeepInfra HTTP 200, one upstream attempt, no fallback, finish reason
   `stop`, 186 input tokens, 185 output tokens including 118 reasoning tokens,
   and a rounded displayed charge of $0.0000383. The local ledger calculates
   **$0.000038332** from published rates. Local request duration was 4.365
   seconds; account generation time was about 3.9 seconds.
3. The local response parser reached the evidence validation step and raised
   `ValidationError`. At that version, this means JSON decoding completed and
   `validate_evidence` rejected the parsed value. The runner marked ledger
   attempt 8 `invalid_response`,
   retained its full **$0.024903544** reservation, and stopped. It did not
   save accepted evidence or retry the request.

**Confirmed failure point:** the model response was received and metered; the
local evidence validator rejected its content. A provider outage, lost POST,
fallback, or length-truncated completion is not supported by this record.
The exact rejected field and text are **unknown**. The historical ledger kept
only `ValidationError`, and OpenRouter I/O logging was disabled. We cannot
recover the response body or say whether the exact quote, entity spans, or
required fields were wrong. The 185 output tokens were below the configured 320-token limit,
but 118 were reasoning tokens. That leaves 67 visible output tokens; the
limit may constrain harder reviews, yet this response reported `stop`, not
length truncation. Token pressure is a hypothesis, not the proven cause.

## Why one invalid row halted the comparison

The original diagnostic runner treated every received invalid response as a
global stop. That was prudent while provider identity, cost, and response
forensics were uncertain, but it made a single content error require manual
account inspection and restart. Strict JSON schema controls the response
shape; it cannot ensure a quote or entity is an exact span in the original
review. The local validator correctly owns that check and must not be
weakened. The first three source reviews were short praise with no named
entities, so their 3/3 quote and entity agreement with saved Codex evidence
was a weak challenge. It did not establish reliability on complaints or
harder spans. This is development agreement, not human-label accuracy.

The incident's immediate accepted-evidence loss was one DeepInfra row. Groq
had not yet processed that row in the interrupted continuation. Known ledger
charges across all attempts are **$0.000205352**. The prior uncertain POST
and this invalid response each retain a full DeepInfra reservation; combined
held exposure is **$0.049807088**, and shared $1-cap exposure is
**$0.049974108**. The earlier POST has no visible settled bill in the
account check, but its delivery and charge remain uncertain. Neither hold
has been released. No 100,000-review run, golden evaluation, or model change
occurred.

## Repairs already made offline

The runner now stores a received invalid response and the specific validator
detail in its ignored local ledger. It keeps metered usage and the full
reservation. The old response is still unrecoverable. A received response
may be skipped only after its request fingerprint, response ID, pinned
provider, normal finish, token bound, and charge are present and valid, and
the failure is `ValidationError`. It is never counted as accepted evidence
and never retried automatically. Uncertain delivery, missing usage, route
mismatch, truncation, catalog/privacy incompatibility, and budget failure
still stop. The original three-total-failure circuit was replaced by a
durable five-consecutive-failure circuit for each route. The historical
first failure remains in the ledger; its full reservation is held.
Reports disclose the 100-source denominator, accepted and failed counts per
route, metered charges including failures, and the number accepted by both
routes. Model comparison must use that paired subset and show coverage loss.
Synthetic tests exercise forensic capture, preserved reservation, skip,
zero automatic retry, and the circuit. They do not prove live quality.

## Recommendations before the next paid segment

1. **Keep the existing controls.** Use the same two pinned providers, exact
   source hashes, strict schema, corrected development baseline, and shared
   sub-$1 ledger. Check endpoint availability, published prices and bounds,
   privacy settings, existing credits, and the read-only plan before dispatch.
   Do not retry either failed or uncertain POST automatically.
2. **Make the next segment diagnostic.** Select a small, predefined group
   from the approved 100 that includes complaints, named features, repeated
   words, punctuation, and long text, alongside one easy praise review.
   Record its selection and source hashes offline. Do not select using golden
   answers or silently change the source set. The current prefix-only runner
   cannot target such a group; add and test selection before using it.
3. **Review the first new invalid response locally.** Its saved validator
   message and response should distinguish malformed JSON, wrong fields,
   paraphrased quote, and non-exact entities. Check that the response kept
   the expected provider, normal finish, usage, and budget hold. If a prompt
   or token setting needs adjustment, version the request fingerprint and
   obtain a separate measured repeat-call decision; do not silently reuse or
   overwrite earlier results. A larger output limit also needs fresh
   published-bound and cap review. The present 320-token limit is not proven
   to have caused this incident.
4. **Gate the following 100-row continuation on evidence.** On the small
   diagnostic segment, require exact-source validation for every accepted
   row, full response/usage recording for any failure, no provider or privacy
   drift, no unknown charge, and exposure strictly below $1. Inspect failures
   by route and difficulty. Five consecutive row-output failures on one route
   pause that route for review. Compare only paired accepted rows against the saved Jev/Codex
   development baseline, and report the attempted, accepted, failed, and
   paired denominators. Do not infer semantic accuracy from agreement alone.

**Remaining uncertainty:** There is no recoverable content for attempt 8,
no measured hard-review success rate, and no complete 100-review comparison.
The prioritized next step is an offline representative-sample selection and
test, followed by a small user-launched segment only after review of the
plan. No paid call was made for this post-mortem.
