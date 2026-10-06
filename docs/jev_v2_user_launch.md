# User launch record for the bounded Jev rubric v2 comparison

The user completed the 100-review v2 launch. The agent's computer control was
denied access to macOS Terminal, and no API key was available in its process.
The user entered the existing key at a hidden-input prompt in a visible
Terminal. The command below is recorded for provenance. **Do not run it
again:** the v2 ledger and result exist, and the launch guard will stop it.

The launcher is `tools/run_jev_v2_user.zsh` on branch
`feat/jev-rubric-v2-comparison`. The user ran:

```sh
zsh '/Users/haniframadhan/Documents/Codex/2026-10-06/task-2/spotify-v2-comparison/tools/run_jev_v2_user.zsh'
```

It checked the unchanged supplied `cost_100.csv` and manifest before prompting.
At `Paste existing TypeSafe key:` the user entered the existing key.
Input echo is disabled. The key is held only in the launch shell and passed to
the one runner process as `TYPESAFE_API_KEY`; it is not in the command line,
shell history, a new credential file, or the results. The launch shell clears
its variable after the runner exits. The runner checks account model access
before any paid call and uses pinned `jev-1.13.0`. It has no top-up or paid
fallback action.

The v1 measured usage-derived cost is USD 0.003691254. The launcher sets the
new v2 ledger cap to USD 0.596308746, so the two ledger ceilings sum to USD
0.60. This is a reservation limit, not an account charge guarantee. The
current published rate is USD 0.042 per million input tokens, output free,
per <https://docs.typesafe.ai/models> checked October 6, 2026. The runner
reserves the 64,000-token maximum before each attempt. No execution beyond
these same 100 reviews is approved.

The ignored `local/jev_pilot_v2.db` is the separate versioned ledger. Successful
aggregate stdout is saved as ignored `local/jev_pilot_v2_run.json`. The
launcher measures its runner process wall time, including the access check,
in ignored `local/jev_pilot_v2_timing.json`. The ledger keeps per-attempt
durations, usage and retry status. The
launcher refuses to start if this ledger or output already exists. Inspect
the prior run before any manual restart. The v1 databases and tracked report
are never opened for writing by this launcher. If the runner fails, inspect
the ledger and any `.tmp` output; do not delete or repeat uncertain calls.

For nonsecret progress, open a second Terminal and run this from the v2
worktree root. It prints only aggregate counts and usage. It makes no call:

```sh
cd '/Users/haniframadhan/Documents/Codex/2026-10-06/task-2/spotify-v2-comparison'
python3 - <<'PY'
import sqlite3
from pathlib import Path
db = Path('local/jev_pilot_v2.db')
if not db.exists():
    print('No v2 ledger yet')
else:
    with sqlite3.connect(f'file:{db.resolve()}?mode=ro', uri=True) as connection:
        print('attempts:', connection.execute(
            'SELECT status, COUNT(*) FROM attempts GROUP BY status').fetchall())
        print('results:', connection.execute(
            'SELECT provenance, COUNT(*) FROM results GROUP BY provenance').fetchall())
        print('settled usage:', connection.execute(
            "SELECT SUM(input_tokens), SUM(output_tokens) FROM attempts WHERE status='settled'"
        ).fetchone())
PY
```

The aggregate result file and offline replay can be read without the key.
The separate v1 and v2 ledgers were compared by
source row hash and ID without exposing review text in the report. Saved Codex
evidence is conditioned on predicted labels; reuse needs per-row label
compatibility and explicit v1 evidence provenance. This launch does not run
evidence extraction, golden evaluation, grouping, ranking, or a memo.

The first completed v2 launch saved an invalid negative wall duration because
the original launcher used monotonic values from two separate Python
processes. The runner now measures access check and paid work with one
process-local monotonic clock. The launcher copies that value into its timing
sidecar after success. The saved first-run value is not repaired or presented
as measured elapsed time. The launch guard remains in place; do not repeat
this run to measure wall time.
