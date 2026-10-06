# Frozen v2 checkpoint 500 preflight

**Decision:** The Jev label checkpoint is prepared offline, but no new review
text may be sent yet. Direct task-user approval for sending the 400 new
development rows to TypeSafe and the distinct new texts to ChatGPT-authenticated
Codex is pending. No 500-row model call has started. This is not a completed
end-to-end pipeline or grader export.

The supplied `checkpoint_500.csv` passed its manifest hash and byte checks.
It has 500 distinct source IDs, and its first 100 six-field rows match the
saved v2 `cost_100.csv` rows exactly. The frozen configuration is
`jev-rubric-v2` with `jev-labels-v1`. The isolated ignored checkpoint ledger
was prepared with those 100 settled labels and exact evidence records. It
retains original Jev attempts and evidence provenance. Its 400 remaining
source rows contain 379 distinct texts not in the saved 100; 21 rows across
the full 500 are exact-text cache candidates. Direct originals must remain
direct sources for cache aliases. There is no golden ID or answer input here.

`tools/checkpoint_500.py --plan` is read-only. `--prepare` creates the
separate ignored copy only once. The explicit `--execute-labels` route is
bounded to at most 400 new rows per invocation, checks source and seed
identity, blocks uncertain attempts and incomplete stages on resume, and uses
the existing Jev pre-call reservation ledger. It is not authorized to run
until the user directly approves the new review transfer and the current
TypeSafe route/rate and key availability are checked. Execution requires a
same-day rate confirmation matching the ledger's USD 0.042/M input rate;
any changed rate requires updating and reviewing the accounting code first.
The key is read only
from the process environment and is never logged or copied by this tool.

The v1 charge was USD 0.003691254 and the v2 charge USD 0.004262454. The
checkpoint ledger cap is USD 0.596308746, leaving the v1 charge outside it;
together they cannot exceed the cumulative USD 0.60 limit through the Jev
reservation mechanism. Current combined measured spend is USD 0.007953708,
with USD 0.592046292 of Jev headroom. At the observed v2 mean input cost,
379 new direct calls would be about USD 0.016154701. That estimate excludes
retries and does not bypass the pre-call cap. If cache coverage differs or an
attempt becomes uncertain, resume requires inspection before more calls.

For Codex entity and supporting-quote extraction, at most 379 new distinct
texts should need new calls if all Jev labels succeed and exact-text cache
reuse remains valid. Previously saved evidence for the first 100 stays
versioned and unchanged. At the old 76-call mean, 379 sequential calls imply
about 2,333 summed attempt seconds, not an end-to-end wall forecast. This is
only a workload estimate: ChatGPT included-plan allowance, token usage,
incremental dollars, failures, and request durations for future calls are
unknown. Pause if the included allowance is unavailable; do not enable an API
fallback, top up credits, or use Claude for these calls. Future Codex JSON
usage and stage timing capture is implemented, but the 500 evidence runner,
full role handoffs, and cold/warm end-to-end measurement are not yet live.

The known development topic concerns do not require another rubric change.
A sparse-genre catalog complaint appears to be a model classification miss;
the skip-limit complaint fits the fixed usability-controls definition. These
are useful quality probes for the checkpoint, not deterministic code defects.
The 500 checkpoint can measure them without human golden labels. No golden
texts or answers were used for tuning.

Remaining after label approval: run bounded Jev labels, extract and validate
new evidence with included-plan Codex, import 500 complete records, run a
blind verifier and save disagreements, group memberships, calculate the
`severity_sum` ranking, write/check the memo, then measure a true cold/warm
end-to-end orchestration and export the contract's grading folder. The
existing synthetic harness checks handoff and cache mechanics only. The
grader export is not implemented; it must pass the supplied checker before
any submission claim.

Read-only hardware check for local-model planning: MacBook Air, Apple M5,
16 GB memory, about 25 GiB available on the 460 GiB data volume at inspection.
Ollama client 0.34.4 is installed, but no server was running. No model was
downloaded or executed. These facts do not change the frozen checkpoint
model choice or imply local inference capacity for 100,000 reviews.
