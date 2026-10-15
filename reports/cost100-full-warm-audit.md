# Full warm orchestration audit

Prepared for local inclusion on 15 October 2026. Publication awaits approval.
This is a new offline replay on a copy of the real saved 100-review pilot.
It does not establish recovery of the historical 110,000-review run.

## Results and provenance

| Measurement | Saved 13 October audit | Repeat on 15 October |
| --- | ---: | ---: |
| Source rows | 100 | 100 |
| Completed / quarantined, before and after | 98 / 2 | 98 / 2 |
| Saved outputs, before and after | 254 | 254 |
| Historical calls, before and after | 112 | 112 |
| New paid / provider transport / socket attempts | 0 / 0 / 0 | 0 / 0 / 0 |
| Full `execute()` time, seconds | 0.020799 | 0.012292583 |
| Whole audit time, seconds | 0.099122792 | 1.356946625 |

Both runs exercised `label`, `evidence`, `verify`, `group`, `rank`, and `memo`
in order. Both retained identical row, output, and call hashes before and after.
The original pilot database was unchanged. These are local timings of saved
work; they are not estimates of fresh model latency or full-corpus runtime.

The [13 October aggregate](cost100-full-warm-audit-2026-10-13.json) is the existing
saved report, copied without changes. The
[15 October aggregate](cost100-full-warm-audit-2026-10-15.json) records this
branch's free repeat. Both use the same code:

- Audit SHA-256: `92268e1d7d35d63c26870cfb9265a5a6f923ab750bc9298856cdcee218f4fc4e`.
- Harness SHA-256: `b2b6a8cf631cc3a87bb0bce9f46711cfb9e4b37c9152371a665cd01a1aadd6ce`.
- Original database SHA-256: `e132ff1360c5337cced0923595d0fda6de34b1db4cc047b176b97efb97a1d7fd`.

## Method

The [audit tool](../tools/audit_cost100_full_warm.py) copies `pilot.db` into a new
private directory. It reconstructs the source CSV only when its bytes match the
pilot's pinned source digest. `open_run()` validates source and configuration.
The tool blocks the harness's paid dispatcher, both provider transports, and
socket connection functions. Any attempted call fails the audit.

It validates saved results with `warm(record=False)`, saves a private checkpoint,
calls the unchanged full `execute()` orchestrator, validates again, and saves
the after checkpoint. Model stages reuse settled outputs; ranking is recomputed.
The two original quarantines are retained without retry or relabeling.

The harness writes the literal phase label `cold` for `execute()` stage events.
Those copied events belong to this new warm experiment. They are not a new cold
benchmark. The published pilot's approximately 0.008029-second `warm()` result
remains a separate cache-validation measurement; it is not replaced here.

## Reproduce with the preserved private pilot

Run from the repository root, with an existing authorized pilot directory and
a new ignored output directory:

```sh
python3 -m tools.audit_cost100_full_warm --pilot <private-pilot-directory> --out local/<new-audit-directory>
```

No keys or provider access are needed. The command refuses an existing output
directory. Source, database, and checkpoint copies remain ignored and mode 0600.
Only aggregate results and whole-file digests are included in this branch.

**Reproduction limit:** a public clone does not contain the private `pilot.db`
required by this audit. Public `cost/pilot/` exports are not automatically
converted into that database. The method and aggregates can be reviewed
publicly; a full repeat requires the preserved private pilot. Do not publish
the database or reconstruct missing historical checkpoints to close this gap.

No new inference, scoring, human labels, cost estimates, or changes to existing
cost files were made. These results add evidence for full warm orchestration
only. Historical main-run recovery and missing grouping usage remain open.
