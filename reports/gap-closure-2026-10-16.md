# Gap closure: verification, grouping, attacks and recovery — 16 October 2026

This report answers the open testing and provenance gaps in the
[rubric assessment](rubric-assessment-2026-10-16.md). Hanif approved one paid run on 16 October and asked
that the new human holdout (human20) not be done. All numbers below come from saved files. The tables are
generated from [`gap-closure-2026-10-16/aggregate.json`](gap-closure-2026-10-16/aggregate.json) and
[`grouping-trail-recovery-2026-10-16/aggregate.json`](grouping-trail-recovery-2026-10-16/aggregate.json).

## What was done

| Gap in the assessment | What this work adds | Criterion |
| --- | --- | --- |
| The 600-case blind verifier trail was not supplied | Recovered the original inputs, outputs and reference key from the 11 October handoff folder. The saved rows reproduce 511 of 600. | D2, T2 |
| Grouping was a chat handoff, not a program stage | A recorded program stage regrouped 600 historical members, blind to their issue, with every request, response, token count and charge saved. | D2, W2 |
| No real independent verifier outcome | A blind verifier relabelled 1,000 accepted reviews from text and rubric only. | T2 |
| No planted-error outcome | Code planted 50 wrong labels and 50 wrong issues in separate copies. An auditor model and the blind outputs were checked for detection. | T2 |
| No prompt-injection outcome | Eight synthetic attack pairs and one contamination batch went through Jev, the evidence extractor, the verifier and the grouping stage. | T2 |
| Jev ran one review per request; the instructor asked for ten | Jev labelled 100 reviews at ten per request, and the verifier ran 1,000 reviews at ten per request. Both were compared with the main run. | W2 |
| No real interruption and resume | The paid run stopped on a real SIGINT, saved a checkpoint, and resumed without resending any settled request. | W2, T3 |

Not changed: the 110,000-review scope, the published ranking, memo and claims, the grading release, and the
original golden 50. No human answer column was read. The full-corpus scope and the deadline remain questions
for the instructor.

## Method

`tools/gap_closure_eval.py` has three commands. `plan` is offline. It freezes the samples, the planted copies
and the synthetic cases into a private plan with SHA-256 identity
`797d89195ac3b918a4ff8fb4bc598ac5291b811377dc02bd7516c3af0b4ed599`. `execute` sends the frozen requests. `report` is offline and writes the
aggregate and the case files.

- **Samples.** A fixed SHA-256 order over the accepted records chose 1,000 reviews for the verifier and a
  separate 600 historical issue members for the grouping stage. Exact duplicate texts were skipped. The 50
  golden IDs and the 100 cost-pilot IDs were excluded by reading only their `review_id` column.
- **Blindness.** Verifier requests hold only `review_id`, `review_text` and the rubric. Grouping requests hold
  the text, Jev's labels and the evidence quote, as the historical grouping did, but not the historical issue.
- **Planted errors.** Code chose 100 verifier-sample reviews and changed 25 topics and 25 severities (by two
  points). It chose 100 grouping-sample reviews and moved 50 to an issue in a different family. The other 50
  in each set stayed unchanged. The auditor saw the claimed value and the text, and said whether the claim
  was supported. Originals were never changed.
- **Prompt injection.** Eight benign synthetic reviews were each paired with an attacked copy that appends
  one attack: label override, forged system message, secret disclosure, format override, ID tampering, a
  hidden HTML comment, a forced issue, and "developer mode". A ninth text tried to relabel every other review
  in its batch. The verifier and grouping instructions for these batches carried a confidential canary
  string to test disclosure.
- **Ledger.** Every call reserved its worst case in the shared project ledger before dispatch and settled its
  usage-derived charge afterwards. A call with no usable answer keeps its full hold until reconciliation.
  The run cap was US$1.50, including holds.
- **Synthetic rows** are excluded from every business result and accuracy figure.

## Results

### 1. Blind verifier, ten reviews per request

The verifier labelled 980 of the 1000 sampled reviews in 100 requests of ten. 98 requests succeeded. Code rejected one that repeated a review ID; it was metered and quarantined. One response arrived but failed the usage check; it stays held and was not resent. Those 20 reviews are left out.

| Field | Agreement with Jev | Cohen's kappa |
| --- | --- | --- |
| Topic | 793 of 980 (80.9%) | 0.69 |
| Intent | 901 of 980 (91.9%) | 0.86 |
| Severity | 837 of 980 (85.4%) | 0.73 |
| All three | 648 of 980 (66.1%) | |

Severity differs by 0.17 points on average. On the 336 reviews Jev called a complaint or cancellation, the verifier also called 319 of 336 (94.9%) negative, and topic agrees on 255 of 336 (75.9%). The verifier cost US$0.017934, about US$0.0000183 per review.

### 2. Jev, ten reviews per request

Jev's API takes a `state` and a map of questions. Jev reads the state once and answers every question. Ten reviews went into one state with forty questions, each pointed at one review by its path, for example `` `reviews[3]` ``. All 10 requests succeeded.

| Field | Same label as the main run's one-review request |
| --- | --- |
| Topic | 79 of 100 (79.0%) |
| Intent | 81 of 100 (81.0%) |
| Severity | 73 of 100 (73.0%) |
| All three | 64 of 100 (64.0%) |

Batching used 852.7 input tokens per review, against 1015.7 in the main run (16% fewer). The rubric instructions repeat for every review, so most of the cost stays. Batching changed at least one label in 36 of 100 reviews, so the main run's one-review labels stay as published. Jev's run-to-run variation on single reviews was not measured here, so part of this change may be ordinary variation. Cost: US$0.003581.

### 3. Grouping as a recorded program stage

The stage mapped 580 of 600 sampled members in 60 requests of ten. Code rejected two requests that repeated a review ID.

| Measure | Result |
| --- | --- |
| Same issue as the historical map | 449 of 580 (77.4%) |
| Same issue family | 503 of 580 (86.7%) |
| Abstained | 3 of 580 (0.5%) |
| Lowest family agreement, 10 or more cases | BIL 30 of 49; CAT 23 of 34; ACC 21 of 31 |

The historical map is not human-validated, so a disagreement does not show which side is wrong. For comparison, the 11 October verifier matched the grouping agents on 511 of 600; see the recovered trail below.

### 4. Planted errors

| Check | Planted labels | Planted issues |
| --- | --- | --- |
| Planted rows scored | 43 (20 topic, 23 severity) | 50 |
| Auditor said the planted value was not supported | 40 of 43 (93.0%) | 48 of 50 (96.0%) |
| Blind output differed from the planted value | 40 of 43 (93.0%) | 46 of 50 (92.0%) |
| Auditor flagged an unchanged value | 5 of 47 (10.6%) | 3 of 50 (6.0%) |

One label-audit request repeated a review ID and code rejected it, so 43 planted and 47 unchanged labels were scored instead of 50 and 50.

### 5. Prompt injection

| Check | Result |
| --- | --- |
| Attacks that reached their target label or issue | 0 of 24 (8 attacks each in Jev, the verifier and grouping) |
| Attacked reviews whose labels or issue changed at all | 0 of 24 |
| Canary string in any response | 0 |
| Evidence extractor | 16 of 16 quotes exact; 0 quarantined |
| Contamination batch, verifier | 1 of 8 benign rows changed; 0 to the attacker's value |
| Contamination batch, grouping | 1 of 8 benign rows changed; 0 to the attacker's value |

Strict JSON schemas and the code's ID check held against the ID-tampering and format attacks. Eight attack types on eight texts is a small test. It shows that these attacks failed here. It does not prove resistance to every attack.

### 6. Interruption and resume

| Measure | Result |
| --- | --- |
| Checkpoint before (UTC) | 2026-10-15T17:40:00 |
| Settled before the interruption | 3 requests; 12 attempts held |
| Checkpoint after (UTC) | 2026-10-15T19:26:17 |
| Settled after resuming | 212 requests; 125 attempts held |
| Settled requests sent again | 0 |
| Every request settled before was still settled after | yes |

A SIGINT stopped the first segment after a burst of HTTP errors. In-flight calls settled, the checkpoint was written, and the process exited 130. The run then resumed from the saved state, and later segments stopped and resumed the same way while the provider was rate-limited. Settled requests were never resent. A request held without a definite answer was never retried.

### 7. Calls, routes and cost

| Measure | Result |
| --- | --- |
| Logical requests | 213 frozen; 212 settled |
| Attempts | 337: 112 HTTP 429 responses, 12 HTTP errors in the first segment whose status code was not yet recorded, and 1 unusable response |
| Metered charge | US$0.040252 |
| Holds without a known charge | US$0.373187, kept in the shared ledger until reconciliation |
| Role calls by route | crusoe/bf16 18, deepinfra/bf16 292 |


**The rate-limit incident.** On 16 October the shared OpenRouter capacity for `openai/gpt-oss-120b` was rate-limited
upstream. The 429 bodies name `engine_overloaded` and `upstream_provider_shared_pool`. The runner kept each
rejected attempt's hold, waited with exponential backoff (45 seconds, doubling up to 10 minutes), and retried
the request under a new attempt key. A timeout or a lost response was never retried. For about 20 minutes the
verifier, grouping and auditor calls used `crusoe/bf16`, the same bf16 weights on another host, with the same
privacy settings. That route was checked against the public catalog for price, parameters and zero data
retention before use, and each call records its route. Ten of the 980 verifier labels came from it. The
evidence-extractor test stayed on the production `deepinfra/bf16` route.

**Charge check.** The cost that OpenRouter reported inside each of the 186 role responses sums to US$0.035982143.
This equals the usage-derived charge the runner computed from token counts and the pinned prices. Jev's
charges (US$0.004270) are usage-derived, as in the main run. The key's account usage figure still lagged when
this report was written, so the holds stay until a later reading shows that the rejected attempts were not
billed.

## Recovered historical verifier trail

`tools/recover_grouping_trail.py` read the 11 October handoff folder. It contains the grouping agents' 159
input batches and their outputs, the verifier's three input batches of 200 and its 600 outputs, and the
private key from opaque references to review IDs.

- All four files that the handoff report hashed still match their hashes.
- The verifier's input columns are `ref`, `topic`, `evidence_quote` and `review_text`. They hold no grouping
  output, and the verifier's references are separate from the grouping references.
- The saved rows give **511 of 600** agreement, the figure the handoff reported, and **323 of 327** where both
  sides marked high confidence.
- All 30,403 grouping outputs match the assembled agent labels, and every input row has one output.
- Usage stays unknown: the agents and the verifier ran in a chat session with no API usage log.

The published case file names each review by the SHA-256 of its ID. It holds no review text and no quote.

## Limits

- Agreement between two models is not accuracy. The only human accuracy figures remain the golden 50.
- The verifier, auditor and grouping stage use `openai/gpt-oss-120b`, the base model of the evidence
  extractor, with separate prompts. They are independent of Jev and of the historical agents, not of every
  model in the pipeline.
- Planted values are wrong by construction. Unchanged values are Jev's or the historical map's, so a flag on
  them is a disagreement, not proof of a false alarm.
- The interruption was a real SIGINT on this run. It does not recreate the missing main-run checkpoint pair.
- The new holdout (human20) was not done, by Hanif's decision.

## What stays open

- **Scope.** The run covers 110,000 selected reviews under the instructor's 100,000 minimum. The unchanged course
  checker still reports `review_required` for the full-corpus formula. Only the instructor can settle this.
- **Main-run checkpoints.** The main run saved no contemporaneous checkpoint pair. This run's real interruption
  shows the mechanism; it does not recreate that history.
- **Historical usage.** The grouping agents and the 11 October verifier ran without an API usage log. Their
  usage stays unknown, not zero.
- **Jev batch size.** The main run's labels came from one review per request. The ten-per-request test above
  shows it is possible with Jev, but it moved labels, so the published labels were not replaced.

## Reproduce

```sh
# Offline: freeze the plan (private output under local/)
python3 -m tools.gap_closure_eval plan --records RECORDS.jsonl.gz --membership membership.csv \
  --source spotify_reviews_18months.csv --exclude golden_50_to_label.csv --exclude cost_100.csv \
  --out local/gap_closure_20261016
# Paid: needs approval, the project Keychain keys and the shared ledger
python3 -m tools.gap_closure_eval execute --out local/gap_closure_20261016 --approved-cap-usd 1.50 \
  --shared-budget-root LEDGER_DIR --interrupt-after 60
python3 -m tools.gap_closure_eval execute --out local/gap_closure_20261016 --approved-cap-usd 1.50 \
  --shared-budget-root LEDGER_DIR --resume
# Offline: the aggregate and case files in this report
python3 -m tools.gap_closure_eval report --out local/gap_closure_20261016 --publish reports/gap-closure-2026-10-16
python3 -m tools.recover_grouping_trail --handoff HANDOFF_DIR --publish reports/grouping-trail-recovery-2026-10-16
```

The case files name each review by the SHA-256 of its review ID. `calls.jsonl` lists every attempt with its
role, outcome, route, tokens, charge and timing, and no review text.
