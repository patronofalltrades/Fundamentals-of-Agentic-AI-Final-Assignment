# Shared ready-queue scheduler: offline handoff

The new `--run-mixed` command uses the existing scale tables, request keys, cache identities, 25-review evidence payload, and atomic `ProjectBudget` reservations. It runs Jev and ready evidence in one eight-slot pool. When both queues have work, it admits up to two Jev calls first and uses spare slots for evidence. Jev defaults to at most four concurrent calls even without a prior overload; `SPOTIFY_JEV_MAX_SLOTS` may explicitly set a value from one through eight, while two prior HTTP 529 holds cap it at four. No higher setting has been used in the live run. Evidence becomes ready only after labels commit. Planned evidence remains in exact source order and retains its size-specific configuration. Provider cooldowns are independent.

An isolated malformed evidence response is charged and quarantined without a retry. Three wholly malformed batches in one run, five consecutive partial/invalid evidence batches, two new uncertain calls for either provider, access failure, or a budget refusal stop new dispatch. Already reserved futures drain and settle or retain uncertain holds. This is a deliberate bounded-quality policy, not acceptance of malformed output.

Offline synthetic tests simulate delayed Jev and evidence calls, overlap, the four-slot Jev overload ceiling, eight total slots, independent evidence cooldown, budget refusal, mixed-stage settlement, stop-and-drain behavior, restart without reissuing uncertain Jev requests, and malformed-batch quarantine. No provider call or credential access occurred. Actual live throughput improvement has not been measured.

## Integration and restart

1. Let the current runner finish or pause through the coordinator. Confirm its process lease is released and no reservation remains `reserved`. Keep uncertain reservations held.
2. Review and integrate this commit into the live branch. There is no database migration or cache identity change. The existing `--run-jev` and `--run-evidence` commands remain available.
3. On a gate with the 25-review evidence configuration already adopted, start the usual coordinator with `--run-mixed` instead of separate Jev and evidence runs. It reads the same pending state and obtains only the credentials needed for work. Do not run it beside another paid runner.
4. Compare accepted source IDs per wall minute, per-stage request times, in-flight occupancy, quarantines, uncertain holds, and budget exposure against the prior gate. If the mixed runner pauses, inspect its saved halt reason and reservations before restarting. No automatic retry of an uncertain POST is allowed.
