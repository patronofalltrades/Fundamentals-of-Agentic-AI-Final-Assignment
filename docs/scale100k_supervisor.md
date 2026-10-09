# Foreground 100k supervisor

After the coordinator integrates and pushes this commit, launch from Terminal in
the live repository checkout:

```sh
cd '/Users/haniframadhan/Documents/Codex/2026-10-07/task-2/spotify-batch10-canary' && caffeinate -i python3 -m tools.scale100k_supervisor
```

Keep that Terminal open. `caffeinate -i` prevents system idle sleep while the
foreground command runs. The command reads the existing secure Jev and
OpenRouter access only when the mixed runner needs it. No key is placed in an
argument or checkpoint. It installs no daemon or login item.
The code uses Python 3.9-compatible standard-library features, including the
tested Mac Python 3.9.6 runtime.

The supervisor holds a separate single-instance lock and the existing paid-run
lease for its full lifetime. A manual scale command or second supervisor will
fail rather than run alongside it. The shared SQLite budget remains the cost
authority; defaults are eight global and four Jev workers. It does not change
caps or model configurations. The adopted measured 25-review, token-aware
evidence mode is required by the mixed runner.

At startup, the supervisor checks the frozen source IDs and hashes, existing
reservations, and saved status. It recovers only previously charged saved
responses through `recover_metered`, whose parser checks original IDs, exact
source spans, usage and response structure. It then invokes the mixed runner
for the current gate. After the runner drains, it checks status and activates
the next 10,000-source gate only when both eligible queues are empty and source
statuses reconcile. It stops at source position 100,000.

A new uncertain request, access or budget failure, unreconciled source, lease
conflict, no accepted progress, or unrecoverable saved response stops the
command. Existing historical uncertain holds remain held and do not alone
block untouched eligible work. A structural quality stop can continue after
validated offline recovery only if accepted labels or evidence increased.
Two consecutive structural quality stops are the maximum; the second stops
for manual review. The counter persists across restarts and resets after a
clean segment. No uncertain request is automatically retried.

Press Ctrl-C once to stop. The signal prevents new dispatch and waits for
in-flight provider calls to settle before releasing the leases. A reservation
that is definitely unsent at handoff is cancelled with its queue record in
one transaction; submitted requests always settle or retain an uncertain
hold. If the process crashes, reserved requests remain visible in the ledger and restart
stops for manual reconciliation. Restart by running the same command after
reviewing its stop reason and ledger. Do not remove the local checkpoint to
bypass a quality stop without reviewing the failed responses.

`local/scale100k_supervisor.json` is an ignored aggregate checkpoint with
source identity, counts, exposure, stop reason, and the quality-stop counter.
The authoritative row and cost records stay in the shared project ledger.
The terminal prints aggregate counts and exposure after each drained segment
or stop. It does not print review text or credentials.
