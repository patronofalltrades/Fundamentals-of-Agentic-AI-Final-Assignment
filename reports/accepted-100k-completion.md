# Accepted-evidence extraction checkpoint

October 9, 2026 UTC. This is an aggregate record of saved development-source
results. It is not a product recommendation, human accuracy score, full-corpus
grading pass, or deployed dashboard result.

## Source accounting

The frozen selection reached **110,000 distinct original source IDs**: the two
earlier 5,000-row checkpoints, the 90,000-row scale selection, and one 10,000-row
extension gate. The second frozen extension gate was never activated. Every
selected ID and original source hash remains accounted for. The paid supervisor
was given a graceful stop when accepted coverage crossed the target; all
in-flight requests settled before it exited. No paid request remains reserved.

| Final source state | IDs |
| --- | ---: |
| Structurally accepted evidence | **100,229** |
| Quarantined structural failures | 1,791 |
| Uncertain or otherwise blocked attempted texts | 1,457 |
| Untouched eligible or awaiting label after target stop | 6,522 |
| Empty source text | 1 |
| **Selected distinct source IDs** | **110,000** |

The 100,229 accepted IDs are 9,566 from the disjoint earlier checkpoints plus
90,663 from the scale queue. Each accepted source has a saved label and
evidence. Code rechecked original source hashes and exact quote/entity spans.
These are structural checks; they do not establish semantic correctness. The
6,522 untouched IDs are pending, not processed or accepted. Quarantined,
uncertain, blocked, empty, and pending IDs do not count toward the target.

## Requests, costs, and exclusions

The scale queue saved 68,417 successful Jev requests and eight uncertain Jev
requests. Its DeepInfra evidence requests have 1,943 succeeded, 703 partial,
90 charged wholly malformed, and 35 uncertain outcomes. Partial and malformed
responses were salvaged only offline for independently validated source-ID and
exact-span rows; raw responses and charges were retained. No uncertain exact
text was automatically retried. The earlier checkpoints add three uncertain
DeepInfra requests. All uncertain reservations remain held at their full
amounts. Historical conservative reservations also remain in the shared
budget exposure.

Across saved scale requests with elapsed time, Jev median request time was
0.319 seconds and evidence median was 35.379 seconds. Scale evidence requests
reported 8,679,886 input tokens and 5,723,812 output tokens, including
1,920,454 reasoning tokens. These request statistics include partial and
charged malformed outcomes; they are not end-to-end dashboard latency.

Measured scale-queue charges are **$2.919711522 Jev** and **$1.294203822
DeepInfra**, including reported reasoning-token charges. Shared cumulative
exposure, including charges and every unresolved or conservative hold, is
**$3.310141884 of the $5 Jev cap** and **$2.469486956 of the $5 OpenRouter
cap**. Known charges and conservative exposure are different measures; no
missing charge is assumed to be zero. SQLite `quick_check` passed and active
reservations are zero.

The private handoff has 100,229 accepted records and 9,771 separate excluded
or pending records. It retains source fields, source hashes, labels, evidence,
configuration and request provenance, source states, request usage, costs,
and the semantic review overlay. Its SHA-256 is
`01d3f466e86f3d6a010f5e9b28b2c1347e683d925228591ff6fa36a2bb75c39c`.
It is git-ignored and owner-readable only. An independent offline validator
confirmed all 110,000 selected IDs, all 100,229 accepted source hashes and
exact evidence spans, the 6,522 pending rows, and the checksum.

There are **47 distinct accepted source IDs with known semantic findings**:
39 from the earlier checkpoint audit and eight from the later 50,000-accepted
pulse audit. Six pulse findings belong to scale rows and two belong to the
earlier accepted checkpoint. All 47 are marked ineligible as representative
evidence pending human review; saved model labels and evidence were not
rewritten. The separate four-row human correction overlay belongs to source
IDs outside this selected frame, so it was verified and recorded without
changing any of these 110,000 outputs. Unflagged rows have not thereby passed
human review. No golden answer labels were read or generated.

## Handoff and remaining gates

Import code should preserve accepted and nonaccepted source partitions, then
validate ID uniqueness, source hashes, provenance, exact spans, and semantic
representative exclusions before materializing a local dashboard database.
Issue grouping, ranking, an independent verifier, a claim-checked product
memo, a deployed backend/dashboard, a live URL, and the course grading export
are still separate work. The instructor-reported 100,000-selected minimum and
this stricter 100,000-accepted target differ from the unchanged full-corpus
grading contract; verify submission scope rather than claiming this checkpoint
passes that checker. Do not publish the private handoff or source reviews.
