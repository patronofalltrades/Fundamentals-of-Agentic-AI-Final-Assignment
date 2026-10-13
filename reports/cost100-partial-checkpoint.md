# Cost-100 pilot result, October 12, 2026

This isolated one-worker run used the unchanged supplied `cost_100.csv` (SHA-256
`c884ac3b9be5066995d5063f96ad9af6e5e082975788c1684c4f6b6ea661dd0e`)
and the approved 41-issue catalog (SHA-256
`8c73e62059e86aea48b94da0d4b0bf86df048e0d83442e1ce4bf7b44dc105111`).
The private saved ledger, records, calls, rates, report, and checkpoints were
copied byte-for-byte from the pilot owner's `local/cost100_pilot/` into
`local/grading_v4_submission_candidate/cost100_pilot_separate/`. This pilot
directory is distinct from the main-run export. No source review text,
original IDs, or golden answers appear in this aggregate report.

| Stage | Calls | Outcome | Recorded API charge |
| --- | ---: | --- | ---: |
| Jev labels | 100 | 100 accepted | $0.004262454 |
| DeepInfra evidence | 4 batches of 25 | 98 accepted, 2 exact-quote failures quarantined | $0.001062133 |
| Blind verifier | 1 | Saved | $0.000190312 |
| Catalog grouping | 6 | Saved | $0.001128357 |
| Deterministic ranking | 0 | Saved | $0 |
| Memo | 1 | Saved | $0.000066485 |

**Total:** 112 metered calls, $0.007410287 charged, 132,136 input tokens,
31,497 output tokens, and zero active local reservations. The offline
calculator recomputes the same API charge from saved usage and dated rates;
all calls have usage. The total is below the user-approved $0.363 pilot cap.
The two failed evidence rows were neither accepted nor retried. The memo and
ranking use 98 accepted evidence rows. This is not a 100/100 successful run.

The first authentic checkpoint has zero completed evidence IDs (SHA-256
`8ea678c52303f274486bd6769e524c9b730276084986fe73218cc4c1adee4dd8`).
The after checkpoint has 98 (SHA-256
`d6a784d5aac21445655fc139ad2f6448a131d05d72541fe8e29ccb4c7b7fe2c5`).
The call export marks 100 initial label calls and 12 resumed calls. Saved
stages replayed without dispatching another provider call.

Cold active stage wall time was 588.435 seconds. First-stage-to-last-stage
wall time was 1,581.190 seconds, including 992.755 seconds of interruptions
and approval pauses; it is not uninterrupted throughput. Warm saved-result
replay took 0.008 seconds and made zero calls. No local compute price was
assigned. The runner does not itself export the course's final `grading/`
layout or establish label accuracy. The two quote failures require inspection
before the result could be called complete.

The [offline calculator](../cost/README.actual-pilot.md) recomputed the saved
API charge as $0.007410287. Doubling all four saved API rates makes it
$0.014820574; changing the projected volume from 100 to 100,000 leaves the
measured pilot fields unchanged. Full-run cost projection is unavailable
without stage-specific scaling assumptions, and local compute cost is unknown.
The aggregate checks are saved in [cost100-offline-checks.json](cost100-offline-checks.json)
(SHA-256 `3e30e6d5f37b43ea3809a4feabe12ec6fd752c30a9d3815c4c2e9c2e4ee0d040`).

The original 0.008029-second warm event read saved outputs, checked coverage,
verifier IDs, ranking, and memo claims, and made no outbound call. A later
read-only validation added source/configuration and cache input hash checks,
exact-quote validation, and grouping coverage. It took 0.019757 seconds with
zero new calls. Neither warm pass regenerated model outputs. These authentic
pilot checkpoints do not replace missing historical main-run checkpoints.
