# Jev questions-per-request: no 32-question limit (batching unblock)

Prepared by OpenCode (Line A) on 2026-10-07 for fix list item 2.1
(`docs/fix_list_2026-10-07.md`). The `feat/jev-batching` worktree caps requests
at 8 rows because it assumes a 32-question provider limit. That assumption is
not supported. Zero model calls were made for this note; all evidence is saved
data and provider documentation checked on 2026-10-07.

## Finding

1. **No documented cap on the number of questions per request.** The Models page
   (https://docs.typesafe.ai/models) states the context rule: "64k tokens per
   request; 32k tokens for `state` plus the longest question." The 64k budget
   covers `state` and all questions combined. The per-question caps it does
   document are option counts, not question counts: a Choice takes up to 255
   options and a Score takes 2 to 10 levels (API reference,
   https://docs.typesafe.ai/api).
2. **Fan-out is the recommended pattern.** Speculative fan-out
   (https://docs.typesafe.ai/patterns/fan-out) recommends putting every
   question your system needs into a single request; questions are evaluated
   in parallel and "adding more questions usually has little effect on
   response time." The parallel-questions cookbook shows 13 questions in one
   call as a routine example.
3. **Saved evidence already proves 180 questions in one request.** The pilot
   ledger `cost/pilot_calls.jsonl` (branch `claude-infra`, Line A) holds five
   successful multi-review Jev calls on `jev-1.13.0`. The largest carried 36
   review IDs, 180 questions and 32,624 input tokens. The fix list note
   already cited this. The required "one bounded test" is therefore already
   on record; no additional live call is needed to settle the limit question.

## What the real limits are

| Limit | Value | Source |
| --- | --- | --- |
| Total request tokens | 64k covering `state` + all questions | Models page |
| `state` + longest question | 32k | Models page |
| Rate limit | 100k tokens/s, 80 requests/s, described as dynamic under load | Models page |
| Options per Choice | 255 | API reference |
| Levels per Score | 2 to 10 | API reference |

## Implications for `feat/jev-batching`

- Drop the 8-row cap. Size batches at 10 reviews per request as the instructor
  clarification requires (grading contract allows 50), guarded by the token
  budget, not by a question count.
- A 10-review batch is small against the caps. Line A measured roughly 830
  input tokens per review at pack sizes 10 to 50 under the five-question rubric
  (topic, intent, severity, sentiment, needs_review), so a 10-row batch runs
  about 8k to 11k tokens and 40 to 50 questions: well inside 64k.
- Keep the existing guard shape in `max_batch_by_tokens`
  (`src/labelling/model_client.py`): estimate the built payload and split when
  it exceeds the 32k `state` + longest-question bound, which is the first
  budget to fill.
- Give a batched request a distinct `label_config` component (the fix list
  already requires the new cache identity). Include the pack size so a later
  repack does not silently reuse old results.

## Quality caveats to keep, not to block on

- **Context rot.** Jev 1.13 jaggedness
  (https://docs.typesafe.ai/model-jaggedness/jev-1.13, last reviewed
  2026-10-02) records that accuracy falls as `state` grows with content
  unrelated to the decision. Each review's question should point only at its
  own text inside the shared batch `state`; the packed questions must name
  their target review, as Line A `src/labelling/prompts.py` already does
  because TypeSafe does not send the question key to the model.
- The fix list 2.1 pass check (compare batched labels with the frozen v2
  one-per-request labels on the same development rows) is exactly the right
  control for this risk. Run it as written.
- Jaggedness also notes Choice options can be order-sensitive. If the
  development comparison shows label drift, test option order before
  concluding batching harmed quality.

## Bottom line

The 32-question assumption does not come from TypeSafe documentation. There is
no documented question-count cap at all; the binding limits are token budgets,
and saved Jev calls already passed 180 questions in one request. Batching at
10 reviews per request is supported. Proceed with the token guard and the
agreement check on development rows.
