# Jev candidate evidence: offline prototype diagnostic

**Status:** One offline prototype and one held-out development diagnostic.
No Jev, Codex, or other model call was made. No credit was spent. The saved
500-review labels and evidence were not changed. The candidate route is **not
ready for the paid 100-review pilot** because its cap rejects many reviews.

## Prototype

[`jev_candidates.py`](../spotify_pipeline/jev_candidates.py) keeps exact source
offsets. It generates Unicode word n-grams of one to five words, quoted spans,
version and device-shaped spans, and punctuation-bearing whitespace units.
Generic case, digit, phrase-length, and English function-word clues rank
entity candidates. It does not contain Spotify feature names or any saved
Codex answer. A quote list contains the full review, clauses, quoted spans,
and short windows. The caps are 96 entity and 16 quote candidates. One quote
Choice, one support-existence Noul, and one independent Noul per entity form
an offline Jev-compatible request. This uses [TypeSafe's documented
candidate-selection pattern](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook)
and [question primitives](https://docs.typesafe.ai/primitives).

The prototype refuses to build a live-style request if either candidate cap
was exceeded. An explicit diagnostic mode can construct that capped payload
for offline sizing. Response parsing rejects bad choice IDs or Noul values,
abstains on quote `none`, negative whole-review support, cap loss, or more
than ten selected entities, and checks exact quote and whole-word entity
spans before returning evidence. It never supplies a fabricated quote.

## Fixed development comparison

The first column uses the same `cost_100.csv` reviews as earlier work. The
second is a deterministic sample: every fourth row among the remaining 400
checkpoint rows, starting at row 101, for 100 separate reviews. Both sets
use saved Codex outputs **only as a comparison reference**. Neither is a
human-labeled accuracy test. The candidate generator was implemented before
running the held-out sample. The earlier cost-100 sketch showed that a simple
32-candidate set missed many saved spans; that aggregate finding informed
this general expansion. No individual Codex answer or golden answer was used
to create a dictionary or rule.

| Measure | Original 100 | Held-out 100 of remaining 400 |
| --- | ---: | ---: |
| Earlier sketch: exact saved entity spans represented | 46 / 93 | Not run |
| Prototype: exact saved entity spans represented | 81 / 93 | 76 / 87 |
| Prototype without 96-candidate cap | 90 / 93 | 84 / 87 |
| Exact saved quote strings represented | 57 / 100 | 56 / 100 |
| Reviews exceeding entity cap | 24 / 100 | 17 / 100 |
| Reviews exceeding quote cap | 4 / 100 | 3 / 100 |
| Selected entity / quote candidates | 4,265 / 443 | 3,631 / 389 |
| Maximum questions in a request | 98 | 98 |
| Serialized request bytes, total / maximum | 872,829 / 21,259 | 746,792 / 20,315 |
| Rough bytes ÷ 4 token proxy | 218,207 | 186,698 |
| Proxy charge at current $0.042/M input | $0.00916 | $0.00784 |

These token and charge values are rough payload-size proxies, **not provider
usage or bills**. The [published rate and limits](https://docs.typesafe.ai/models)
could change before a live run. A maximum of 98 questions has not been
provider-tested. It fits the documented 64,000-token request budget by the
local byte proxy, but that does not prove a server token count or successful
acceptance. Quote-string overlap is low because Codex can select arbitrary
short source substrings; a different candidate may be valid. Only a future
semantic development review can judge that.

Of the saved entity spans absent from the *uncapped* prototype, three in the
original 100 and one in the held-out 100 are longer than five word spans.
Two further held-out misses contain punctuation. The remaining nine original
and eight held-out entity mismatches occur when the 96-candidate ranking
truncates a longer review. There are 43 and 44 saved quotes respectively
that the quote generator does not reproduce exactly, even without its cap.
These are categories of disagreement with Codex, not human error counts.
No multilingual recall claim is possible from these aggregate comparisons;
unsegmented scripts and partial word boundaries require a dedicated review.

## Gate and alternative

This fixed version exposes an unfavorable tradeoff: candidate coverage rises
from 46/93 to 81/93 on the original 100 and reaches 76/87 on the separate
sample, but 24% and 17% of reviews exceed the entity cap and therefore cannot
receive a complete result. Raising the cap further would increase Noul
questions and payload size, while arbitrary quote spans remain uncovered.
Do not run the proposed paid 100-review pilot with this version.

A Jev-compatible next design is a bounded **hierarchical candidate sweep**:
split long reviews into exact source clauses or windows, ask independent Noul
questions on at most 96 candidates per request, then combine accepted IDs in
code with a strict per-review request and token cap. Keep a separate quote
Choice with a `none` option; if no candidate supports the labels, abstain.
This avoids silent truncation but may require multiple Jev requests for long
reviews. A small offline feasibility pass should count requests, candidate
coverage, and worst-case reservations before any live call. If long or
unsegmented reviews still exceed that budget, leave them pending for human
review rather than claiming full coverage. No 100,000-review run is supported
by this prototype.
