# Decision record: keep Jev, and fix the timing risk

Date: 2026-10-06, updated 2026-10-07 for the instructor clarification. Decision owner: Hanif. Written by Claude (Line A infrastructure) at Hanif's request.
This file adds a decision and a plan. It does not change code, ledgers, or earlier reports.
Numbers marked **measured** come from saved files in this repository or from saved Line A runs.
Numbers marked **projection** are linear estimates, not reservations or approvals.

## 1. Decision

1. **Jev stays the classifier for `topic`, `intent` and `severity`.** The frozen rubric is
   `jev-rubric-v2` with schema `jev-labels-v1`.
2. **No switch to a hosted open-weight model or a local model.** Section 5 records the measured
   alternatives and why they were not chosen.
3. **Scope (updated 7 October 2026).** The instructor clarification sets the minimum at 100,000 source
   reviews; the full corpus is a stretch goal. `GRADING_CONTRACT.md` still describes all 660,622 IDs, so
   disclose the gap. See `AGENTS.md` and the README, section 2.
4. **The deadline is 13 October 2026, 23:59 PT.**

## 2. Why Jev stays

- **Price.** Jev input is USD 0.042 per million tokens. Output is free
  ([TypeSafe models](https://docs.typesafe.ai/models)). Measured charges here are small: the 500-row
  checkpoint added USD 0.016147992 for 379 calls (`reports/checkpoint-500-readiness.md`).
- **Stability.** In three repeated Line A runs on the same 50 reviews, topic changed on 1/50, intent on
  1/50, and severity on 0/50.
- **The contract starts from Jev.** `COST_CALCULATOR.md` §1 says to use Jev first for fixed topic,
  intent and severity choices. A replacement needs a measured evaluation to justify it.

The problem is **time**, not model price.

## 3. Timing risk (measured, then projected to 484,189 distinct texts)

| Stage, current route | Measured | Projection for the full corpus, one stream |
|---|---|---|
| Jev labels, one review per request | 379 calls in 127.0 s label-stage wall time (0.335 s per review) | about 45 hours |
| Codex evidence, one call per review | 379 calls, 2,567.5 s summed (6.77 s per review); 6,955,138 reported input tokens (about 18,350 per review) | about 910 hours, and about 8.9 billion input tokens |

Exact-text reuse already lowers 660,609 nonempty reviews to 484,189 distinct texts. The Codex route
cannot finish in time even with heavy parallelism. Its ChatGPT-plan cost is unknown, and
`COST_CALCULATOR.md` says plan access is not evidence that programmatic calls are free.

## 4. Mitigation plan

### 4.1 Batch Jev requests

- The instructor clarification asks for **10 reviews per request**. `GRADING_CONTRACT.md` allows up to 50.
  Validate every returned ID. Save after each batch.
- Size each batch by a token budget. Line A uses a 32,000-token budget, which gave 36, 36 and 28
  reviews for `cost_100.csv`.
- **Line A measured, same 100 reviews, same Jev model:** 3 requests, 2.69 s enrich-stage wall time,
  90,629 input tokens. Another cold run took 6.25 s. Projection: about 4 to 8 hours for the full
  corpus with one worker.
- Batching changes the request shape. Give it a new `label_config` and cache identity. Run a measured
  pilot on development rows. Compare its labels with the frozen one-per-request v2 labels on the same
  rows before you scale.

### 4.2 Build evidence in code; cap model evidence

- `COST_CALCULATOR.md` §1: "a short review's complete original text can be its evidence quote;
  explicitly matched feature terms can form an entity list."
- **Line A method** (`src/labelling/extract.py`, version `extract-v2`):
  - Entities: a whole-word keyword lexicon. Only terms that occur in the text.
  - Quote: the whole text if it has 300 characters or fewer. Otherwise the first sentence with a
    matched entity term. Otherwise the first sentence.
  - **Measured on all 660,622 rows:** 52 s in total, no model calls, every quote an exact source
    substring.
  - Limit: a keyword can be mentioned without being the complaint.
- Use Codex only for a **declared, capped** fraction of hard cases, for example at most 1%. At the
  measured 6.77 s per review, 1% of 484,189 texts is about 9 hours in one stream.

### 4.3 Run safely

- Keep save-after-each-batch and resume without resending completed IDs. This also produces the
  required interrupt and resume evidence.
- Use bounded retries with backoff. TypeSafe returned HTTP 503 on 14 of 15 calls during one Line A
  attempt on 2026-10-06. Budget time for outages.
- Use 2 to 4 workers at most, with one shared rate limiter and one spend cap. Check TypeSafe rate
  limits first.
- Keep the Mac awake during long runs: run the command under `caffeinate -i`, on mains power.

### 4.4 Gates and dates

| Date | Gate | Decision |
|---|---|---|
| 6–7 Oct | Batched Jev and code evidence on development rows; true end-to-end cold/warm 100-row pilot | Batching keeps label agreement with the frozen v2 labels |
| 7 Oct | Verify, issue mapping, `severity_sum` ranking, memo, grading export work end to end | Mechanical self-check passes on the pilot |
| 8 Oct | 10,000-row development run; refresh the projection | **Go/no-go:** start the 100,000-review run only if the projection is under about 24 hours |
| 9 Oct | 100,000-review run, resumable, in the background | Leaves time for outages and resumes |
| 10–11 Oct | Full corpus, only if measured time and cost allow | Stretch goal only |
| 11–12 Oct | Export, self-check, human memo review, recording | — |
| 13 Oct | Buffer only | — |

**Start the 100,000-review run by 9 October at the latest.**

## 5. Alternatives measured or considered (not chosen)

| Route | Measured or quoted | Why not chosen |
|---|---|---|
| Local Ollama `gemma4:e2b-mlx` on this Mac (Apple M5, 16 GB) | **Measured** on 20 and 50 development rows from `checkpoint_500.csv` (not golden): JSON output 0.96 s per review; compact `id,T,I,S` output with thinking off 0.63 s per review | About 85 to 129 hours for the full corpus. Quality not measured. Local compute cost must be recorded as unknown, not zero. |
| Hosted open-weight models (Groq, Cerebras, DeepInfra, Together) | **Quoted, unverified** aggregator prices of roughly USD 0.05–0.15 per million input and 0.08–0.30 per million output tokens | Needs a new provider, a new cache identity, a measured pilot, and a quality check. Free tiers have daily caps far below the corpus size. |

## 6. Other open points

- `needs_review` is true on 387 of 500 checkpoint records. The declared rule flags every `other`
  record (289). A flag on 77% of records carries little signal. Review the rule before the full run.
- Human golden evaluation: Line A scored Jev against the 50 human labels and adjudicated
  disagreements against the contract rubric. Line A branch `claude-infra`, files
  `evals/golden_50_human_labels.csv` (adjudicated), `evals/golden_50_human_labels.original.csv`,
  `evals/golden_adjudication_log.csv`, `evals/reports/golden-jev-summary.md`. Use the adjudicated CSV,
  not the `.xlsx` working copy: the `.xlsx` has one quote with a trailing space that is not a source
  substring. Report both label sets and disclose that the adjudication followed model predictions.

## 7. Line A references (pushed branch `claude-infra` on `origin`)

Use these as references. Port them to this pipeline's SQLite state, or adapt their logic. Do not copy
output files.

| Need | Line A file |
|---|---|
| Batched Jev with token-budget sizing | `src/labelling/model_client.py` (`max_batch_by_tokens`) |
| Batch validation, retry → split → quarantine, resume | `src/pipeline/enrich.py` |
| Code evidence (`extract-v2`) | `src/labelling/extract.py` and `tests/test_labelling_extract.py` |
| Issue mapping and `severity_sum` ranking that match the checker | `src/pipeline/group.py`, `src/pipeline/rank.py` |
| Claims and memo checks | `src/pipeline/claims.py` (`lint_memo`), `src/pipeline/memo.py` (prompt `memo-v3`) |
| Grading export and self-check | `export_grading.py`, `src/pipeline/export.py` |
| Cost calculator, cold/warm and projections | `cost/cost_calc.py`, `cost/README.md` |
| Golden scoring with the checker's own code | `evals/score_gold.py`, `evals/build_gold.py` |
