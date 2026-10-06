# Jev rubric v2 versus v1: same 100 development reviews

The user ran rubric v2 on the unchanged supplied `cost_100.csv`. This report
compares its saved ledger with the earlier v1 ledger, read-only. The
machine-readable aggregates are in `jev-rubric-v1-v2-100.json`. Recompute it
from the repository root with:

```sh
python3 -m tools.compare_jev_pilots \
  --input PATH_TO_COST_100 --manifest PATH_TO_MANIFEST \
  --v1-db PATH_TO_V1_LEDGER --v2-db local/jev_pilot_v2.db \
  --timing local/jev_pilot_v2_timing.json \
  --out reports/jev-rubric-v1-v2-100.json
```

This reads the two local ignored ledgers and sends no model request. No human
golden answers were read.

## Validation and spend

Both ledgers contain the same 100 original IDs, exact texts and source row
hashes. Each has 100 direct results from 100 settled attempts, with no retry,
cache copy or uncertain attempt. The source file hash matches the supplied
manifest. The model is `jev-1.13.0` in both runs. The prompt changed from
`jev-rubric-v1` to `jev-rubric-v2`; the output schema stayed `jev-labels-v1`.
The configuration hashes differ, so v1 results were not reused as v2 labels.

| Saved measure | v1 | v2 |
| --- | ---: | ---: |
| Input tokens | 87,887 | 101,487 |
| Output tokens, free at listed rate | 19,656 | 19,652 |
| Usage-derived Jev cost, USD | 0.003691254 | 0.004262454 |
| Sum of request durations, seconds | 42.076869542 | 37.275935833 |
| `needs_review` true | 73 | 75 |
| Topic `other` | 47 | 58 |
| Saved evidence records | 100 | 0 |

V2 used 13,600 more input tokens and cost USD 0.000571200 more than v1, a
15.47% increase in usage-derived cost. Combined usage-derived Jev cost is
**USD 0.007953708**, below the cumulative USD 0.60 limit. The v2 ledger cap
was USD 0.596308746 after v1's measured cost. These figures apply the
[listed TypeSafe rate](https://docs.typesafe.ai/models) of USD 0.042 per
million input tokens, with output free. The provider credit debit was not
independently reconciled. No top-up or paid fallback was used by this runner.

The v2 timing sidecar saved **−0.043681375 seconds**, an invalid wall-clock
result. Its launcher used monotonic values from two separate Python processes;
on this machine those values are not comparable. The saved sidecar is left
untouched and v2 end-to-end wall time is **unknown**. The request-duration sum
is a different measure. The launcher source was corrected for future use, but
the guard prevents repeating this completed run.

## Label movement

| Field changed between v1 and v2 | Rows |
| --- | ---: |
| Topic | 32 |
| Intent | 0 |
| Severity | 1 |
| Sentiment | 69 |
| `needs_review` flag | 16 |

The review flag turned on for nine rows and off for seven. Topic `playback`
fell from 19 to 7; `usability` rose from 10 to 14; `other` rose from 47 to
58. The most common changed path was `playback` → `usability` (eight rows).
All transition counts, including less common paths, are in the JSON report.
The unchanged intent counts do not prove intent accuracy. The 69 sentiment
changes show that changing one question's rubric can affect other answers in
the same model request; they are not evidence of improved sentiment quality.

The v1/v2 topic distribution is: `access` 2/2, `billing` 6/7, `catalog`
12/10, `downloads` 3/2, `other` 47/58, `playback` 19/7, `support` 1/0,
and `usability` 10/14. The `needs_review` distribution is false 27/25
and true 73/75. These are raw model outputs, not verified category rates.

Manual reading of **development** rows found several intended boundary
changes: a crash and a stuck loading screen moved to `playback`; missing
offline lyrics moved to `catalog`; ad interruptions moved to `usability`;
generic listening praise and a paid-plan mention without a billing problem
moved to `other`; and “support” used as endorsement moved out of customer
support. These are selected, unblinded judgments against the written contract,
not a scored sample. There are also unresolved concerns. A complaint about
missing music in a genre moved from `catalog` to `other`, and a complaint
about blocked playback controls moved from `playback` to `usability`. Some
control restrictions sit near the contract's playback/usability boundary.
The larger `other` count warrants review before scaling. No claim of higher
accuracy, F1, or human agreement is made.

## Evidence provenance and next gate

The v1 ledger has 100 saved Codex evidence records: 90 from evidence prompt
v1 and 10 from evidence prompt v2. The extraction prompt included **topic,
intent, severity and sentiment**. Its quote was selected to support those
predicted labels. Automatic reuse therefore requires exact source text and
all four prompt-label values to match. Confidence and `needs_review` were
not sent to extraction and are not part of this predicate. Exactly **24**
rows meet it and have structurally valid v1 evidence. Of these, 21 carry
evidence prompt v1 and three carry evidence prompt v2. The original v1 and v2
Jev ledgers remain intact. A separate ignored v2 evidence working copy now
contains these 24 exact-span records with explicit `reused_v1_exact_four_labels`
provenance and zero new-call elapsed time. They are not presented as newly
extracted v2 output.

The other **76** are not automatically reusable: 44 changed sentiment only,
seven changed topic only, 24 changed topic and sentiment, and one changed
topic, severity and sentiment. Intent never changed. One of the 24
label-identical rows changed its `needs_review` flag, which does not affect
the extraction input. A changed sentiment may leave a quote useful, but exact
source-span validation alone cannot establish that it supports the new tone.
The strict predicate is conservative rather than proof that all 76 need a new
model call.

The no-call next step is to inspect the 44 sentiment-only cases for semantic
quote support, then inspect the 32 topic-related cases against the new topic
and written contract. Existing exact quotes and entities can be retained only
with a recorded manual judgment and their original v1 evidence prompt/model
provenance. A full original review can be a deterministic exact quote and an
empty entity list is schema-valid, but these choices still need a semantic
check; they must not be labeled as Codex extraction. Only unresolved cases
would be sent to the already authorized ChatGPT-auth Codex route, at most
**76** single-review calls, with v2 labels, the existing bounded evidence
schema, and fresh v2 provenance. This is a plan, not an execution or a claim
of zero provider cost. The first attempted new extraction was rejected by
automatic approval review before its process started. The stated reason was
that it would send a private Spotify review to an external ChatGPT-authenticated
service and the authorization visible to the reviewer did not directly cover
new extraction. No review was sent. The working copy still has **24 evidence
records, 76 missing and zero new evidence attempts**. Do not rerun this action
through another route; provide the direct authorization evidence to the
approval reviewer first.

This comparison is a development check on 100 rows. It is not the required
end-to-end cold/warm pilot, a verifier run, issue grouping, ranking, memo, or
human golden evaluation. The golden source has known exact-text overlap with
development data, documented in `docs/topic_rubric_v2.md`; no human answer
labels were accessed here. Do not scale to 500 reviews from these results.
