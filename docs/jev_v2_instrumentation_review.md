# V2 instrumentation and development review

This pass used saved `cost_100.csv` artifacts and synthetic fixtures only. It made
no model calls, read no human answer labels, and did not change the v1 or v2
label ledgers. The original 76 Codex evidence attempts remain successful.

## Measurements and limits

The Codex extractor now requests the CLI's JSON event stream. It keeps only
nonnegative `input_tokens`, `cached_input_tokens`, and `output_tokens` from a
completed-turn usage event. Event payloads are discarded. New evidence attempts
save those three counts when present; missing usage stays null. No dollar amount
is derived from ChatGPT plan usage. The v2 evidence runner also saves an
in-process monotonic whole-stage duration for each new invocation, including
failed or partial invocations. Its preexisting 76 attempts have no saved Codex
token counts or stage wall time; these values remain unknown. Their measured
summed attempt duration is 467.882031003 seconds, which cannot be substituted
for stage wall time. The separate Jev v1/v2 measured usage-derived charges
remain USD 0.003691254 and USD 0.004262454, respectively.

The no-network synthetic harness exercises source ingestion, a bounded Jev
stub, exact-text cache, evidence and cache provenance, import, a verifier stub
that sees only original text, grouping, `severity_sum` ranking, and memo stub.
It measures cold and warm whole-pass and stage durations in one process. Its
two invented reviews collapse to one direct classifier and one evidence stub
call; warm execution makes zero stub inference calls. This checks orchestration
and saved-state reuse only. The verifier, grouping and memo roles are stubs;
there is no live end-to-end 100-review wall or full-pipeline cost measurement.

## Fixed-contract development reading

The saved v2 labels contain 58 `other`, 14 `usability`, 10 `catalog`, seven
`billing`, seven `playback`, two `access`, two `downloads`, and zero `support`.
Severity counts are 48 at 1, 23 at 2, 20 at 3, nine at 4, and zero at 5.
`needs_review` is true on 75 rows; all 58 `other` rows are flagged by the
declared rule. These are raw predicted labels, not category prevalence or
accuracy. V1 to v2 changed topic on 32 rows and the review flag on 16.

Selected development cases support several intended topic repairs: a crash
and loading failure map to playback, missing lyrics to catalog, an ad
interruption to usability, and generic praise to other. Two notable unresolved
cases are a complaint about missing music in a genre mapped to `other` and a
complaint about blocked playback controls mapped to `usability`. The first
looks like a likely catalog miss under the fixed rubric. The second is a
playback/usability boundary judgment requiring independent review. The large
`other` bucket may include more missed specific issues; this pass did not
score or exhaustively relabel it. These are unblinded manual development
judgments, not human-gold evaluation or a quality estimate. The deterministic
checks found no source/schema/cache mapping defect; the remaining topic
concerns are model judgments or rubric boundaries. The earlier negative v2
wall-time sidecar was an instrumentation defect and is not repaired
retroactively.

## Next gate

Keep the 500-review decision on hold. The smallest useful live experiment is
a bounded, independently blinded verifier pass on roughly 12–20 development
reviews, selected before seeing verifier answers to cover `other`/catalog,
playback/usability, praise, and severity 3–4 boundaries. It should receive
original text and the fixed rubric without Jev's first prediction, save
disagreements and usage, and have its own explicit spend limit. The existing
100-row labels and evidence can then support a real cold/warm orchestration
pilot with grouping, ranking and memo once those roles and cost controls exist.
Neither experiment was run here.

For scale context only, a linear extrapolation of v2 Jev label charge is
USD 0.021312270 for 500 fresh direct calls, or USD 0.017049816 for 400 new
calls if the first 100 are reused and all new calls match the observed mean.
These are label-only estimates. Retries, duplicate caching, evidence,
verification, grouping, memo, wall time, and Codex plan usage remain unknown.
The estimate does not authorize 500 calls or imply the full pipeline is cheap.
