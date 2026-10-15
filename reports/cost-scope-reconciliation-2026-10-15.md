# Cost-scope reconciliation — 15 October 2026

## Exact reconciliation

The old “about $4.20” headline rounded the **scale queue only**. Its exact known
charges were **US$4.213915344**. The grading release includes that queue plus
two earlier checkpoint stages, totaling **US$4.725972366** in known charges.
The difference is **US$0.512057022**, exactly the two earlier stages below.

| Saved request table | Jev calls | Evidence calls | Jev known charge (USD) | Evidence known charge (USD) | Combined (USD) |
| --- | ---: | ---: | ---: | ---: | ---: |
| `checkpoint_requests` | 4,099 | 85 | 0.174531378 | 0.065068805 | 0.239600183 |
| `next5000_requests` | 3,999 | 418 | 0.170293284 | 0.102163555 | 0.272456839 |
| `scale_requests` | 68,425 | 2,771 | 2.919711522 | 1.294203822 | 4.213915344 |
| **Export total** | **76,523** | **3,274** | **3.264536184** | **1.461436182** | **4.725972366** |

The [9 October completion report](accepted-100k-completion.md) explicitly names
scale-queue charges and 90,663 accepted scale rows. The earlier checkpoints
contributed the other 9,566 accepted rows. Costs count requests and metered
failures, not only accepted rows; these are different denominators.

## What was verified

The shared ledger was opened read-only with `query_only=ON`; `quick_check`
returned `ok`. Each of the three request tables was joined to its reservation
by request key. Its per-stage call count and sum of known reservation charges
match the exported `calls.jsonl` exactly. The file's SHA-256 is
`179c8b808324cb733cc2b85fb25d504f1472167638f80856161f82174d252661`.
It matches both the release and the published [call aggregate](run-110k-calls-aggregate.json).

[The exporter](../tools/export_actual_main_calls.py) records each source table
and uses reservation charges. The first checkpoint table has no own charge
column; the reservation is its charge source. The later two tables also carry
their own charge columns, which match the reservation sums. No new charge was
estimated, no raw provider response was opened, and no ledger was modified.

[PR #31](https://github.com/patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment/pull/31)
already corrected the headline and cost documentation. This report adds an
exact independently checked breakdown. Existing `cost/` files are unchanged.

## What these totals exclude

- Null charges stay unknown. The export has 46 calls with no known charge;
  47 calls have unavailable input/output usage (94 fields). These are not zero
  cost and are not the same count.
- Unresolved reservations and conservative historical holds are exposure,
  not metered charges. The 9 October report's US$5.779628840 combined exposure
  has a different scope and must not replace or be added blindly to these totals.
- The separate golden-gap run, independent cost pilot, coding work, and missing
  historical grouping/verifier/memo usage are outside this main-call export.
  Neither headline is a complete project bill.
- Durations in the call export are per-request elapsed times. Their sum is not
  end-to-end runtime when workers overlap.

All 76,523 Jev calls contain one review. Evidence payloads vary by stage: the
first checkpoint includes 50-review calls, the next checkpoint uses up to ten,
and the scale queue uses up to 25. The final 25-review configuration must not
be described as the maximum for all 3,274 historical evidence calls. This is a
scope qualification for the cost owner's current batching summary.

The [closeout aggregate](submission-closeout-checks-2026-10-15.json) saves the
counts, charge subtotals, missing-usage counts, and payload-size histograms.
It contains no source IDs, review text, answers, or credentials.
