# Verifier and grouping sample completion

**Local result. Publication is not approved.**

Hanif approved a new separate one-time US$0.33 allowance and the specified data
sharing at 00:18:20 UTC on 16 October 2026. The frozen manifest covered only the
remaining 20 verifier reviews and ten grouping members. Its digest is
`186397d8243b8dbe278949e503049ed1ef8c844f9adeb792c58a31e37655a9e3`.

Execution used local commit `bc7a91a61420b435d265cd70a476e33637928c53`.
The fresh preflight confirmed the pinned route, prices, privacy settings,
existing credits and shared provider headroom. No credits or account settings
were changed.

## Coverage and measured agreement

| Saved sample | Before this run | After |
| --- | ---: | ---: |
| Verifier outputs | 980/1,000 | **1,000/1,000** |
| Grouping outputs | 590/600 | **600/600** |
| Label auditor outputs | 100/100 | 100/100 |
| Issue auditor outputs | 100/100 | 100/100 |
| Changed-label cases with both auditor and blind output | 48/50 | 50/50 |
| Changed-issue cases with both auditor and blind output | 47/50 | 50/50 |

All three batches passed on their first attempt. No retry, invalid response or
uncertain delivery occurred in this run. The original selected IDs and sample
denominators are unchanged. Earlier invalid outputs remain rejected and saved.

Verifier agreement with Jev is topic **808/1,000**, intent **917/1,000**, severity
**853/1,000**, and all three **660/1,000**. Cohen's kappa is 0.6918, 0.8585 and
0.7301 respectively. Mean absolute severity difference is 0.176 on the 1–5 scale.

Grouping matches the historical issue on **462/600** and the issue family on
**522/600**; **3/600** abstain. The historical 511/600 verifier experiment is a
separate comparison. Its unrecorded token usage remains unknown.

The blind verifier disagrees with 47/50 changed-label claims; blind grouping
disagrees with 50/50 changed-issue claims. Both joins now have full coverage.
The auditor results are unchanged: 46/50 changed-label claims flagged, 7/50
unchanged-label claims flagged; 48/50 changed-issue claims flagged, 3/50 unchanged
issue claims flagged. These are machine-claim experiments, not human accuracy.

## Cost and preserved evidence

| Measure | Result |
| --- | ---: |
| Attempts | 3 of at most 9 |
| Known charges | US$0.000809700 |
| New unresolved holds | US$0.000000000 |
| New exposure | US$0.000809700 |
| Separate approved ceiling | US$0.330000000 |
| Earlier follow-up holds, preserved | US$0.216267600 |

Charges use the larger of saved provider cost and usage times pinned prices.
This is metered cost, not a later invoice reconciliation. Old holds are not
reclassified as free. Both US$5 provider caps are unchanged.

The route was OpenRouter to Crusoe `crusoe/bf16`, `openai/gpt-oss-120b`, low
reasoning, strict JSON schema, 4,096 maximum output tokens, concurrency one,
no fallback, required parameters, ZDR and data collection denied. Response ID
enums bound each request to its ten original IDs. Code still required exact
identity, order and fields; no inferred mapping or partial-batch salvage occurred.

Response rate headers are saved privately. Both subsequent admissions occurred
after the persisted minimum cooldown. No HTTP 429 occurred, so this run does not
measure live Retry-After recovery. Synthetic tests cover seconds, HTTP dates,
restart persistence and stopping for waits over 300 seconds. It also does not
prove that cooldown or ID enums caused success.

Original plan and database fingerprints, every prior follow-up file, and all
historical shared-ledger rows and caps are unchanged. New requests, raw receipts,
validated outputs and usage are private, mode 0600 and ignored by Git. Human
answer files were not read by the executor or report builder.

The [safe aggregate](measurement-completion-2026-10-16.json) is rebuilt read-only
from the saved requests and receipts. It rechecks ID validation, usage-derived
charges, provider-reported charges, request/response hashes, cooldown ordering,
before/after metrics and preservation fingerprints. Historical reports remain
unchanged; the dashboard registry adds each run as a separate source.

## Publication scope and remaining limits

The local package updates the evaluation cards, source-scoped verification
summary and the pipeline's grouping caption. It keeps original, first-follow-up
and completion charges separate. Completed coverage gaps are removed; old
billing gaps and model-comparison limits remain visible.

These are selected samples of the existing main run. Full sample coverage is
not full-corpus verification or population accuracy. The 100,229 accepted rows,
golden-50 diagnostic scores, attribution, issue ranking and product memo are
unchanged. The full-course checker remains `review_required` for its unchanged
660,622-row contract and historical evidence gaps. No database import, release,
push, merge, deployment or course submission occurred.

## Validation

- Full Python suite: 463 tests run; 461 passed and two expected private-fixture
  skips. No test failure.
- Registry, original measurement aggregate and completion aggregate checks
  reproduce their saved files. CLI help passes.
- Frontend: two-page build, 36-file typecheck with zero errors/warnings/hints,
  and four Node tests pass. Validation used the same Mac's existing offline
  dependency copy; all 47 tracked frontend files match. No dependency or lockfile
  change was made.
- Local browser: complete verifier/grouping and paired coverage, preserved
  golden-50 display, three separate cost columns, old holds and matching pipeline
  caption verified; zero console errors. The preview contained aggregate fixtures
  and no original review text.
- Independent ledger/privacy check: three new settled rows total US$0.000809700;
  every old ledger row/cap and original artifact fingerprint still matches.
  All 21 changed public files were scanned for original IDs and source text.
  Private run and manifest files remain mode 0600 and Git-ignored.
