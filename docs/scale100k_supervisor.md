# Foreground accepted-evidence supervisor

Hanif's October 9 target is **at least 100,000 accepted evidence rows for
distinct source IDs**. Selecting or accounting for 100,000 IDs is insufficient.
The original frozen source manifest covers positions 10,001–100,000 after the
two earlier 5,000-ID checkpoints. An optional, separately frozen extension
covers positions 100,001–120,000. The supervisor activates source positions
in 10,000-ID gates only when the preceding gate has drained, and stops after a
drained gate reaches the accepted target. A frozen source scope that runs out
first stops for review. Quarantined, uncertain, invalid, empty, or synthetic
rows do not count as accepted. The earlier 9,566 accepted rows are verified
against the ledger and counted once. The separate $5 provider caps do not
change with the source extension.

After the coordinator integrates and pushes this commit, launch from Terminal in
the live repository checkout:

```sh
cd /path/to/spotify-batch10-canary && /usr/bin/caffeinate -i /usr/bin/python3 -B -m tools.scale100k_supervisor
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
statuses reconcile. A source extension must be frozen from the unchanged
supplied source before its first gate activates. The shared ledger pins its
digest in the same transaction as source activation. Optional frozen
positions are not paid or selected until a gate is activated.

A new uncertain request, access or budget failure, unreconciled source, lease
conflict, no accepted progress, or unrecoverable saved response stops the
command. Existing historical uncertain holds remain held and do not alone
block untouched eligible work. A structural quality stop can continue after
validated offline recovery only if accepted labels or evidence increased.
Two consecutive structural quality stops are the maximum; the second stops
for manual review. The counter persists across restarts and resets after a
clean segment. No uncertain request is automatically retried.
The checkpoint also retains the previously observed uncertain-request count.
A restart stops before dispatch if that count changed after a crash. After
reviewing a quality stop or changed uncertain count, explicitly resume with
`python3 -B -m tools.scale100k_supervisor --resume-reviewed` under the same
foreground `caffeinate -i` wrapper. That flag acknowledges the reviewed stop
and updates the baseline; it is rejected when no review is needed.

Press Ctrl-C once to stop. The signal prevents new dispatch and waits for
in-flight provider calls to settle before releasing the leases. A reservation
that is definitely unsent at handoff is cancelled with its queue record in
one transaction; submitted requests always settle or retain an uncertain
hold. If the process crashes, reserved requests remain visible in the ledger and restart
stops for manual reconciliation. Restart by running the same command after
reviewing its stop reason and ledger. Do not remove the local checkpoint to
bypass a quality stop without reviewing the failed responses.

`local/scale100k_supervisor.json` is an ignored mode-0600 aggregate checkpoint
with source identity, counts, exposure, stop reason, the quality-stop counter,
and the acknowledged uncertain-request count.
The authoritative row and cost records stay in the shared project ledger.
The terminal prints aggregate counts and exposure after each drained segment
or stop. It does not print review text or credentials.
