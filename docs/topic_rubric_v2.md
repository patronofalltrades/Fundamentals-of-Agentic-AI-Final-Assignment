# Jev topic rubric v2

Hanif approved this wording revision for the fixed eight-topic grading contract. It changes the topic Choice prompt from `jev-rubric-v1` to `jev-rubric-v2`; the output schema stays `jev-labels-v1`. The saved 100-review pilot used v1 and was not relabeled. No v2 model call or quality measurement has run.

| Topic | v2 Choice meaning |
| --- | --- |
| `access` | Login, signup, passwords, or account access. |
| `usability` | Navigation, layout, controls, queue or playlist management, or ad interruptions. |
| `playback` | Playing, pausing, skipping, shuffling, crashes, loading failures, lag, audio or connection failures, or resource use. |
| `downloads` | Downloading music, saved downloads, offline listening, or disappearing downloads. |
| `catalog` | Missing music, artists, or podcasts; search, discovery, recommendations, or lyrics availability, including missing offline lyrics. |
| `billing` | Prices, charges, subscriptions, paywalls, premium entitlement, or explicitly premium-only controls. A paid-plan mention alone is insufficient. |
| `support` | Customer-service contact or response, rather than support meaning endorsement of a cause. |
| `other` | General praise or criticism, unrelated or unclear text, or no supported specific topic. Generic music-app praise stays here. |

For multiple problems, choose the highest supported severity, then the first specific problem mentioned if tied. For praise, choose the first specific praised feature; general praise is `other`. The agreed boundary cases are loading failures → `playback`, missing offline lyrics → `catalog`, and generic “great music app” praise → `other`. The contract's eight labels are unchanged. These instructions are not deterministic relabeling code; they guide a future model call.

The v2 prompt version changes `label_config()`, its configuration hash, and the exact-text cache key. The pilot ledger refuses to open a different configuration. The completed-import path also rejects saved rows whose configuration hash differs from the current rubric. The historical v1 report and ignored saved databases stay untouched.

The current `tools.jev_pilot --replay` is version-specific and will reject the old v1 ledger under v2 code. The old aggregate report remains readable; a historical ledger replay needs the v1 code. This preserves provenance while preventing an old label from appearing as a fresh v2 result.

## Evaluation boundary

Hash-only comparison used the untouched blank `golden_50_to_label.csv` source and exact UTF-8 review-text bytes, with no case or whitespace normalization. Golden text was hashed in memory but never displayed or used for rubric tuning. No completed human answer file or human answer label was accessed. Development and golden review IDs do not overlap.

| Development file | Golden rows with an exact-text match | Distinct shared texts |
| --- | ---: | ---: |
| `cost_100.csv` | 2 | 1 |
| `checkpoint_500.csv` | 4 | 3 |
| `analysis_10000.csv` | 6 | 5 |

One of the 47 development-pilot `other` texts inspected during rubric review matches an exact text used by two golden rows. Do not use golden answers or these overlaps for rubric tuning. Preserve the original 50-case evaluation and report its full metrics; also report overlapping-text and unseen-text strata separately. No golden cases were redrawn or removed.

## Offline checks

The full standard-library test suite passed 161 synthetic/offline tests, and `python3 -m spotify_pipeline --help` succeeded. The default 100-review Jev dry run verified the pinned sample and manifest, built 100 planned requests, and reported `live_calls: 0`, `measured_usage: null`, and `measured_runtime: null`. Its 298,038 serialized request bytes and USD 0.003129378 four-bytes-per-token illustration are planning estimates, not v2 usage or a bill. A read-only check confirmed the saved 100-result ledger matches v1's configuration hash and differs from v2's. No model calls, relabeling, database edits, or publication occurred.
