Current criterion-based assessment: [Course rubric assessment — 16 October 2026](rubric-assessment-2026-10-16.md).
# Submission benchmark against the course requirements — 13 October 2026

This report compares the project, as merged on `main` at `cec5be9`, with the written course requirements:

- the course dataset `README.md`;
- `GRADING_CONTRACT.md` (machine-checkable evidence, v1);
- `COST_CALCULATOR.md` (the T3 cost deliverable);
- the instructor's in-class clarification, as reported in [AGENTS.md](../AGENTS.md): a minimum of 100,000 source
  reviews, plus a deployed dashboard, a backend, a database and a live URL.

**Limit of this benchmark.** The scored rubric is on the course site (`assignment5.html`), which is not in this
repository. The contract says only that an overall "4/3/3 rubric" applies and that the cost calculator is item T3.
This report therefore checks each written requirement. It does not predict a grade.

Status values: **Met**, **Partly met**, **Not met**, **Disclosed gap** (not met, with a stated reason). All checks
were run on 13 October 2026 (UTC) without model calls.

## Summary

| Area | Status | Main gap |
| --- | --- | --- |
| A. Pipeline program and agent roles | Partly met | The 100k grouping ran as Claude Code subagents, not as a saved program stage |
| B. Scope and source accounting | Disclosed gap | 110,000 selected IDs versus 660,622 in the unchanged contract |
| C. Common labels | Met | — |
| D. Enrichment batching, caching, saved state | Met, with flags | 20,938 rows with split cache/evidence provenance |
| E. Interruption and resume | Partly met | No main-run checkpoints; the demo video (in the release) uses synthetic data |
| F. Grading folder and self-check | Met, with flags | Published as a release asset; checker gives `review_required` |
| G. Baseline ranking and claims | Met | Ranking is advisory; the separate 40% comparison used assistant manual assignments against human answers, not production grouping predictions |
| H. Memo and recommendation | Met (provisional) | Model-derived; numbers checked, meaning not human-validated |
| I. Cost calculator (T3) | Met | Full-run time is modeled, not measured |
| J. Human golden evaluation | Met | Diagnostic only; development-text overlap |
| K. Dashboard, backend, database, live URL | Met | — |
| L. Reproducibility for graders | Met | Fixed on 13 October: two tests needed a private file |
| M. Budget | Met | — |

## Detail

### A. Pipeline program and agent roles — Partly met

| Requirement | Evidence | Status |
| --- | --- | --- |
| A saved program takes an input CSV path and runs ingest, enrich, verify, group, rank and recommend without manual chat pasting | Ingest, enrich, rank and claim checks are saved code. The cost pilot ran all six stages as a program on `cost_100.csv`. The 100k issue grouping was done by eight Claude Code subagents, and a blind verifier, run from a chat session | Partly met |
| Distinct model roles with saved inputs and outputs | Jev `jev-1.13.0` labels; DeepInfra `openai/gpt-oss-120b` evidence quotes; a separate blind verifier; grouping; memo. Saved per stage | Met |
| Code owns IDs, hashes, accounting, cache, ranking and claim checks | Yes: `spotify_pipeline/`, `tools/`, `dashboard/` | Met |

**Risk.** The contract says "A chat transcript or memo alone does not demonstrate the pipeline". The grouping
outputs are saved and audited, but the 100k grouping step was not a program stage. The README discloses this.

### B. Scope and source accounting — Disclosed gap

- Contract: all 660,622 IDs, 660,609 classified, 13 empty texts quarantined.
- Run: 110,000 selected IDs, all accounted for: 100,229 accepted, 1,791 quarantined, 1,457 uncertain or blocked,
  6,522 pending, 1 empty.
- The instructor's clarification sets a 100,000-review minimum. The unchanged checker reports 550,622 missing IDs.
  The README and the [prepublication audit](prepublication-reconciliation-2026-10-12.md) disclose this.

### C. Common labels — Met

The export uses the contract's exact `topic`, `intent` and `severity` labels. The rubric is frozen as
`jev-rubric-v2` ([topic rubric v2](../docs/topic_rubric_v2.md)). Stars are not used as labels.

### D. Enrichment batching, caching, saved state — Met, with flags

- One review per Jev request (76,523 requests), not the 10 the instructor asked for; evidence requests carried up to
  25 distinct texts (3,274 requests). The contract allows up to 50. Every returned ID is validated.
- Results are saved after each batch, with a shared spend ledger and pre-call reservations.
- 4,569 rows reuse exact-text results through valid direct `cache_source_id` links.
- **Flag:** 20,938 completed rows have label and evidence origins that are split or indirect. The checker cannot
  represent them as one direct origin. They are kept as they are and disclosed.

### E. Interruption and resume — Partly met

| Requirement | Evidence | Status |
| --- | --- | --- |
| Interrupt after saved progress, resume with no new calls for completed IDs | Cost pilot: `checkpoint_before.json` has 0 completed IDs, `checkpoint_after.json` has 98, and 12 resumed calls sent no completed ID again | Met for the pilot |
| The two checkpoint snapshots of the main run | Not saved during the historical run | Not met |
| A short recording | `synthetic-interruption-resume-demo.mp4`, a real offline SIGINT and resume with synthetic data and mock responses. Attached to the [release](https://github.com/patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment/releases/tag/grading-2026-10-13) | Met, with synthetic data |

A recording of a real resume, for example on the cost pilot's saved state, would be stronger evidence than
synthetic data.

### F. Grading folder and self-check — Met, with flags

- The contract files, plus `ingestion.json` and `manifest.json`, are published as `grading-110k.zip` in the
  [release `grading-2026-10-13`](https://github.com/patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment/releases/tag/grading-2026-10-13). They come from the private candidate
  (`local/grading_v4_submission_candidate/`): 110,000 records, 79,797 main-run call records, seven declared
  human label corrections. Before publishing, every file was scanned: no credentials, connection strings or
  local paths.
- The main-run `checkpoint_before.json` and `checkpoint_after.json` do not exist and are not supplied. The pilot
  checkpoints in `cost/pilot/` do not replace them.
- The unchanged `check_submission.py` returns `review_required`. It reports no ingestion, record schema,
  membership, ranking or claim flag. Every other flag is listed with its count and disposition in the
  [prepublication audit](prepublication-reconciliation-2026-10-12.md).
- Hanif approved publishing the original review IDs and exact quotes from the CC0 dataset.

### G. Baseline ranking and claims — Met

- Complaint and cancellation records only, one issue each (`allow_multi_issue: false`), 30,400 members.
- `priority_score = severity_sum`, descending, then issue ID ascending; means to six decimals, half-up.
  Recomputed independently; the checker reports no ranking flag.
- 164 claim IDs in `claims.csv` all match the saved ranking.
- **Caveat:** the issue map is model-made. Separately, assistant manual assignments agreed with human answers on 16 of 40 (40%); this did not evaluate the production grouping model. The
  ranking is advisory, and the README and the memo say so.

### H. Memo and recommendation — Met (provisional)

The [provisional memo](provisional-product-priority-memo.md) cites claim IDs for every issue-level number. It
recommends a targeted human review of the leading issue (`USE-ADS`) before a product change. It makes no revenue,
churn or causal claim. Numeric consistency does not prove that the issue map is correct.

### I. Cost calculator (T3) — Met

The contract scores T3 as 1 when all three parts are shown, 0.5 for materially incomplete evidence, 0 when absent.

| Part | Evidence | Status |
| --- | --- | --- |
| (a) Real 100-review cold/warm pilot, all costs and failures counted | 112 calls, US$0.007410287, 98 accepted, 2 quarantined, warm run 0.008 s with zero calls | Met |
| (b) Offline calculator with working arithmetic and editable assumptions | `python3 -m tools.cost100_offline_calculator` recomputes the charge; doubled rates double it; the projected count does not change the measured results. Full-run estimates added on 13 October (below) | Met |
| (c) Retry, spending and recovery controls | Reservations, uncertain-call holds, no automatic retry of unknown outcomes, checkpoints | Met |

Added on 13 October, offline with no model call:

1. **Full-run estimates** for all 660,622 rows (`--scenario cost/scenario_full.json`). With and without
   exact-text reuse (484,189 distinct texts), in a base and a conservative case. The budget, retry and fallback
   fractions, verifier sample, output growth or cap, and maximum concurrency are all editable. A scenario above
   the budget is flagged. Results: US$35.11 to US$62.89, and the last case is flagged. Projected to 110,000 rows,
   the base estimate (US$5.85) is close to the main run's measured US$4.21.
2. **`pilot_records.jsonl`** and unredacted calls and checkpoints with the 100 original IDs. The IDs match
   `cost_100.csv` in order. Hanif approved this.
3. **Pilot execution commands** for `tools/cost100_harness.py` in `cost/README.md`.
4. **The scaling decision**: the budget, batching, concurrency, fallback and spend controls (`cost/README.md`,
   section 4).

### J. Human golden evaluation — Met

All 50 predictions were frozen before scoring. Exact agreement: topic 26/50, intent 38/50, severity 30/50, all
three 14/50; severity MAE 0.56; zero missing. Live on the dashboard since 13 October, marked `official: false`.
Twelve human rows ask for review, and eight texts overlap development data, so this is a diagnostic. The
instructor scores against a private sample.

### K. Dashboard, backend, database, live URL — Met

Checked 13 October 2026: every route below returned HTTP 200 in 0.15 to 1.1 seconds.

- **Pages:** `/` and `/memo/`.
- **API:** `/api/summary`, `/api/issues`, `/api/memo`, `/api/claims`, `/api/recommendations`, `/api/evals`
  and `/api/reviews`.

The summary reports 110,000 source rows and 100,229 completed. The issue list has 41 issues. The memo status is
`claims_checked_provisional`, and the golden evaluation shows as saved. The backend is a Python WSGI function on
Vercel. The database is Neon Postgres `dashboard_100k`, loaded from an audited public copy.

### L. Reproducibility for graders — Met

- On a fresh clone, `python3 -m unittest discover -s tests -t . -q` gave 2 errors. Two tests in
  `tests/test_golden_gap_runner.py` read a private file under `local/`. They now skip when that file is absent.
  The suite runs 408 tests: OK, 2 skipped.
- The offline cost calculator runs with no key.
- `python3 -m spotify_pipeline --help` works.

### M. Budget — Met

Measured main-run charges were US$2.92 for Jev and US$1.29 for DeepInfra. The total stays well below the US$50
ceiling and the instructor's expected US$10 for 100,000 reviews. The grouping agents' token usage is unknown,
not zero.

## Actions before the deadline (21 October, 23:59 Pacific)

| # | Action | Owner | Status |
| --- | --- | --- | --- |
| 1 | Publish the grading folder and the video as release assets | Hanif | Done: release `grading-2026-10-13` |
| 2 | Add full-run estimates, a pilot execution command and a scaling decision to `cost/` | Claude | Done |
| 3 | Include the 100 pilot review IDs in `cost/` | Hanif approved | Done: `cost/pilot/` |
| 4 | Submit the public GitHub URL through bCourses | Hanif | Pending |
