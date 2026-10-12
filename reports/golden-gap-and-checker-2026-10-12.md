# Golden prediction and grading checkpoint — 12 October 2026

This report uses only aggregate results. Private source IDs, review text, model
responses, human answer rows, and the public-reference mapping remain under
ignored `local/` files with mode 0600. Nothing was pushed or deployed.

## Approved golden prediction run

The frozen blank 50-row source and source-only 41-row gap plan were verified by
SHA-256 before inference. Four compatible exact-text results were imported from
saved direct origins. One compatible saved Jev label from a prior charged
partial evidence attempt was reused. The runner made exactly 36 new Jev
`jev-1.13.0` requests and two DeepInfra/bf16 `openai/gpt-oss-120b` evidence
batches of 25 and 12 reviews. An executor disconnect interrupted the first
25-review evidence attempt after reservation but before a response was saved.
Its delivery and charge are unknown, so the full reservation remains held.
With the user's specific approval, one new attempt for those same 25 reviews
settled successfully. No other request was retried.

| Saved request state | Calls | Measured charge or full hold |
| --- | ---: | ---: |
| Jev settled | 36 | $0.001534134 charged |
| DeepInfra settled | 2 | $0.000575591 charged |
| DeepInfra uncertain | 1 | $0.006938624 held |
| **Incremental charged plus held** | **39** | **$0.009048349** |

The separate existing $5 provider caps and shared project ledger still apply.
The uncertain hold was not cleared. The 39 entries in the private calls log
and the per-attempt before/after snapshots belong to this golden gap run only;
they do not reconstruct historical 100k-run checkpoints. Six focused safety
tests passed, including crash after reservation, one-attempt idempotency,
cache provenance, and a named one-time retry. The keys were obtained through
the existing Mac Keychain entries, never printed or saved.

All 50 source-only predictions were frozen before opening the human answer
file. `local/golden_gap_run_20261012/predictions50_frozen.jsonl` has SHA-256
`42bbc688c71648206cde882c7d4eb72f8ecf8c5154298f5520ce645427228d44`.
The isolated code-local evaluator reports 50 completed predictions, 52% topic
agreement, 76% intent agreement, 28% exact topic–intent–severity agreement,
topic macro F1 0.339156, intent macro F1 0.442381, severity MAE 0.56, and
sentiment MAE 0.21. Severity agrees exactly on **30/50** cases; twenty differ.
Twelve human rows carry `needs_review=true`. Topic support, topic confusion,
absolute severity-error distribution, and agreement-pattern counts are saved
in a separate private aggregate report (SHA-256
`68a199ce254950ce14981c980faa3d831fa6dd109749a3d721ffdaa113deea58`).
No per-case answers entered model context. Eight of the 50 source texts match
development texts, including four newly completed cases; the earlier nine
also have mixed evidence configurations. The four-field evaluator does not
score entity or evidence-quote accuracy. These diagnostics do not prove
population accuracy.
Any revision influenced by these golden answers needs a fresh untouched
holdout before a final accuracy claim. Freezing this prediction file before
the current score does not prove that older prompt or catalog decisions were
never influenced by golden feedback.

## Grading candidate and unchanged checker

The private 110,000-row candidate now includes authentic source-ingestion
profiling and **79,797 actual main-run call records** joined to their atomic
reservations. Saved null usage and unknown phases remain null; per-call elapsed
seconds are not summed as wall time. The candidate completed rows were filled
from the verified accepted handoff with saved sentiment, entities,
`needs_review`, and label configuration; 1,791 saved quarantine reasons were
restored. Seven human label corrections and all source hashes were preserved.
The original candidate bytes were snapshotted privately. Of the accepted
rows, 4,569 carry an actual single direct exact-text cache origin; split or
indirect origins were not rewritten. The private candidate manifest explicitly
marks main-run before/after checkpoints, verifier/group/memo call records,
and phase metadata unavailable.

The unchanged course checker ran against a **scoped diagnostic reference**
built from the saved, source-matched 110,000-ID manifests. It returned
`review_required`, with 100,229 structurally valid completed records, 1,791
quarantined, 7,980 other nonaccepted states, and 4,569 valid cache reuses.
Membership, baseline ranking, and numeric claim checks produced no flags.
Remaining checker flags are 7,980 invalid statuses, 949 nonbinary saved call
outcomes, 79,797 unknown run phases, 94 missing usage fields, unavailable
main-run resume snapshots and missing verifier/group/memo role records, plus
the unfinished classification and call-coverage gates. The checker counts
20,938 completed records without representable direct call or unified direct
cache provenance. Most are saved exact-text aliases whose label and evidence
origins differ; assigning a convenient new origin after the fact would change
their provenance. Those are genuine evidence or scope
gaps; the exporter did not invent calls, statuses, phases, tokens, or
checkpoints to silence them.

| Remaining flag | Type | Honest resolution |
| --- | --- | --- |
| 949 nonbinary call outcomes | Saved-status format differs from checker enum | Preserve original partial/quarantined/uncertain status; a future adapter would need per-call and per-row outcome evidence before any binary mapping. |
| 7,980 selected nonaccepted statuses; unfinished classification | Actual incomplete selected work | Keep all selected IDs; do not relabel pending or uncertain rows as completed or quarantined. |
| 79,797 null run phases; missing initial/resume proof | Historical metadata absent | Obtain authentic request-to-checkpoint associations; timestamp gaps cannot supply them. |
| 94 unavailable token fields | Provider usage unavailable | Keep null; no zero-filled usage. |
| 20,938 unlogged completed records | Split or indirect cache provenance not representable by checker | Preserve saved label/evidence origins and original call evidence; do not assign a post hoc unified origin. |
| Two missing main-run checkpoints; missing verify/group/memo roles | Historical execution evidence absent | Supply only if authentic artifacts are recovered. A new cost-pilot checkpoint is separate. |

The original full-source reference command could not read even the CSV header:
macOS reports the 93 MB source file as `compressed,dataless` with zero local
blocks. Two Desktop copies of the same CSV and two dataset ZIPs were also
offloaded and had zero local blocks. No materialized local copy was found.
The scoped reference was independently assembled from saved private
manifests and matched to the accepted handoff. It is **not** the official
660,622-ID full-file reference. The candidate run declares 110,000 selected
IDs, 100,229 accepted IDs, and notes that its pinned analysis hash identifies
the original full source, not a reconstructed selected analysis CSV. The
unchanged full-corpus checker cannot be claimed as passed under this scope.

The checkpoint, next-5000, and scale request tables have no run-phase field.
Their shared reservations save creation time but not the associated before/
after completed-ID snapshot. Seven saved resume log files name no request
keys. Timestamp gaps and attempt numbers therefore cannot prove an individual
call's `initial` or `resume` phase. All 79,797 phase values remain null rather
than being inferred. The original provider outcomes remain in the call file;
949 partial, quarantined-metered, or uncertain outcomes do not fit the course
checker's binary successful/failed enum. Ninety-four token fields remain
unavailable, never zero-filled.

The free verification tests added in this integration worktree are synthetic
identity, exact-span, and public-boundary checks. They are not a real planted
error replay, model injection-resistance test, or independent semantic review.
