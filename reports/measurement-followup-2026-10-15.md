# Bounded follow-up: saved results and offline diagnosis

Prepared 16 October 2026. This is a local publication candidate. The aggregate
registry is updated locally; publication requires approval.

This report preserves the first follow-up's result. The later
[completion run](measurement-completion-2026-10-16.md) reached verifier
1,000/1,000 and grouping 600/600. Its results and charges are separate.

## Saved results

The separately approved US$0.38 run used all ten attempts on 15 October UTC.
Two batches passed validation. Two metered responses failed ID validation.
Six requests returned HTTP 429. No further request was made for this diagnosis.

| Measurement | Before | After |
| --- | ---: | ---: |
| Blind verifier valid outputs | 980/1,000 | 980/1,000 |
| Grouping valid outputs | 580/600 | 590/600 |
| Label auditor valid outputs | 90/100 | 100/100 |
| Changed-label cases with both auditor and blind outputs | 41/50 | 48/50 |
| Changed-issue cases with both auditor and blind outputs | 46/50 | 47/50 |

The verifier scores are unchanged: topic 793/980, intent 901/980, severity
837/980 and joint 648/980. Grouping matches the historical map on 454/590 exact
issues and 512/590 issue families; 3/590 abstain. These are model comparisons.
They do not measure human accuracy. The historical 511/600 experiment is separate.

The label auditor flags 46/50 changed claims: 24/25 changed topics and 22/25
changed severities. It flags at least one field on 7/50 unchanged claims.
The latter are model disagreements, not proven false positives. The unchanged
issue auditor flags 48/50 changed claims and 3/50 unchanged claims. Synthetic
injection results are unchanged.

Of the paired changed-label cases, the blind verifier disagrees on 45/48.
For issues, blind grouping disagrees on 47/47 paired cases. Missing cases are
excluded from agreement denominators and remain visible as coverage gaps.

**Correction:** an earlier private handoff reported 48/50 paired label cases
before the follow-up. That counted blind outputs without requiring an auditor
output. The correct before count is 41/50 selected cases. The historical public
report's 41/43 uses its 43 observed auditor cases; that report stays unchanged.

## Charges and holds

| Measure | US dollars |
| --- | ---: |
| Known metered charges | 0.001146700 |
| Six unresolved reservations | 0.216267600 |
| Total new exposure | 0.217414300 |
| Separate approved ceiling | 0.380000000 |

Each metered charge uses the larger of provider-reported cost and usage times
pinned prices. Both amounts are saved. HTTP 429 charges remain unknown; all six
full reservations remain held. Unused monetary allowance does not extend the
exhausted ten-attempt authorization. Historical charges and holds stay intact.

## Rate-limit diagnosis

All six error bodies identify Crusoe and `upstream_provider_shared_pool`.
The exact rate limit is unknown. Response headers were not saved by the executed
runner. Retry-After presence and whether the timing happened to satisfy it are
unknown. The executed runner had no header handling or backoff. Its next request
was admitted about 0.24–0.33 seconds after each 429 settlement. The causal effect
of these rapid retries is unmeasured.

Raw bodies remain private. They contain account metadata and are unsuitable for
public reports. The new aggregate exports only selected metadata, counts and hashes.

## Invalid IDs and safeguards

The rejected verifier response had ten rows: nine exact expected IDs and one
unknown ID, leaving one requested ID missing. The rejected auditor response had
ten expected-ID occurrences, but only nine distinct IDs: one duplicate and one
missing ID. Neither response has a complete one-to-one mapping.

No complete deterministic repair exists. Position, similar spelling, or assigning
the omitted ID would guess the source association. Both whole batches stay rejected.
No nine-row salvage is counted. Original responses, outputs and denominators stay intact.

Future runner safeguards now capture only Date, Retry-After and rate-limit
headers. They persist a global cooldown across retries, batches and restarts.
The minimum interval is 45 seconds after a response. A 429 or 5xx uses the greater
of 45 seconds and parsed Retry-After, including HTTP dates. An in-process wait
over 300 seconds stops with a durable resume time. Other reset-header formats are
saved but not guessed. Old databases are rejected without migration.

A proposal helper adds the ten exact input IDs as an output-schema enum and
checks the conservative context bound. It preserves the original request and
creates a different hash. Strict validation still rejects duplicates, unknown
or missing IDs and extra fields. This is an offline safeguard; no live result
for the changed schema is claimed. A fresh manifest and approval are required.

## Evidence and remaining work

The [aggregate](measurement-followup-2026-10-15.json) contains all ten safe receipt
summaries, before/after comparisons and source fingerprints. Its builder opens
saved databases read-only, revalidates request hashes and accepted outputs, and
matches raw receipt bytes to the saved ledger. Human answer files are not read.

Twenty verifier rows and ten grouping members remain missing. The
[completion proposal](measurement-completion-proposal-2026-10-16.md) targets full
sample coverage. It does not require perfect agreement. The main 100,229 accepted
rows, golden-50 scores, attribution and full-course `review_required` status are
unchanged. No production database, release or submission was changed.
