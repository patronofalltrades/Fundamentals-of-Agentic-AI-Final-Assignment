# Evaluation attribution and local inclusion handoff — 15 October 2026

**Subsequent closeout:** PR #30 merged and its automatic production release
succeeded. A broader search recovered the older agent-label audit aggregates;
see [verified provenance](grouping-score-provenance-2026-10-15.md) and the
[current submission checklist](final-submission-checklist-2026-10-15.md).
The preparation and narrower missing-file findings below remain historical.

Owner: Codex. Branch: `docs/evaluation-attribution-memo-warm`.
Base: published main `1217b47be344a3a145ab6e5bb9922ba24d58d705` (PR #29).
Reviewed changes commit: `fdaa77844959cb982c04fa6aa3cff200d2553b00`.
The follow-up commit records the late-arriving verification result below.
The rubric assessment is already on main. This branch is local and awaits
publication approval. Existing worktrees, cost files, private answers, scores,
membership, ranking, claim values, and release artifacts are preserved.

## Correct interpretation of 40%

The [source report](issue-grouping-independent40-score.md) records one
assistant's manual issue assignments compared with human answers:

- Exact issue agreement: **16/40 (40%)**.
- Issue-family agreement: **21/40 (52.5%)**.
- Five human answers have uncertainty notes.
- The assistant's predictions were saved and hashed before scoring.
- Aggregate human family counts were visible before prediction freeze.
- The sample contains five cases per saved topic; it is not a prevalence sample.

No production grouping model produced that prediction file. This comparison
does not measure production grouping accuracy. Its prediction-file SHA-256 is
`68e6782c47795394b69f1ea351cd6db6d28300e8cbba4d0d82e0d19a8c5ba7b5`.
This review read the report and scoring code, not human answer columns.
It did not make predictions or rerun either human score.

The historical **511/600 (85.2%)** result remains separately attributed to
model-to-model agreement between grouping agents and a blind model verifier.
Its missing per-case verifier trail remains a limitation. It is not human
accuracy. The 51 pilot and 40 human override cases are no longer untouched
holdouts for final membership.

### Separate historical claim requiring provenance review

Two older reports claim a production-agent comparison with the same **16/40**
exact total. The triage report claims **22/40** family agreement, whereas the
assistant report records **21/40**. Their code selects `agent_labels_v1.csv`;
the assistant report names its separate frozen prediction file. Identical exact
totals do not establish identical predictions or provenance.

The older reports now carry a dated attribution warning. Their historical
scores, tables, artifact hashes, and scorer logic are preserved. The older
private aggregate files were not present at their reported relative paths in
the preserved checkout inspected for this task. This review did not recreate
them, read human answer columns, or assert that the old score was false.
Recover and inspect the authentic aggregate/input provenance before using
that separate claim. Do not relabel its 22/40 family total as the assistant's
21/40 result.

## Public wording reviewed

The current-facing 40% wording now names the assistant manual comparison in:

- `README.md` (results and quality disclosure).
- `web/src/lib/reflections.ts` and `web/src/components/dashboard/memo-panel.tsx`.
- `dashboard/static/app.js` and both tracked provisional memo copies.
- `tools/export_grouping_v4.py` (future generated memo prose only).
- The grouping handoff, submission status, coordination record, older rubric
  benchmark, and free-verification report.

The two old production-agent reports retain their separate historical claims
with the warning above. The independent40 source report now names the assistant
at its heading and prediction description. The already-correct offline
verification report remains unchanged. Unrelated mentions of human agreement
in the golden registry, pilot documentation, and tests remain unchanged.

The screenshot manifest now identifies the old wording as historical and
supplies the correction. Screenshot pixels and hashes are preserved. The
rubric assessment gets a local-preparation addendum; its original criterion
statuses and historical checks are preserved.

## Inclusion decisions

| Item | Local decision | Evidence and limits |
| --- | --- | --- |
| Expanded decision memo | Prepared for review in `reports/product-decision-memo-2026-10-13.md` | Retains ads discovery, playback alternative, tradeoffs, hypothesis, outcome/guardrails, and stop conditions. Public top-five values and totals match release `ranking_public.csv`. Links now use published artifacts. No review text or original IDs. It does not replace the deployed memo or claim ledger. |
| Full warm audit tool | Include the existing `tools/audit_cost100_full_warm.py` unchanged | Its hash matches the saved 13 October report. A free 15 October repeat passed with all six stages and zero paid/transport/socket attempts. No new inference. |
| Warm reports | Include method, original aggregate, and new repeat aggregate | Only aggregate counts, timings, method, and file/table digests. A public clone lacks the private `pilot.db` required to repeat it. These audits are new warm experiments, not historical main-run recovery. |
| Existing cost calculator/rates/pilot files | Preserve unchanged | New warm evidence is separate and does not replace the original cache-validation timing. |
| Human20, golden answers, private source/database/checkpoints | Exclude | No answer inspection, new labeling, rescoring, or publication is authorized. New private audit files remain ignored and mode 0600. |
| Other local diagrams, flow generator, remediation plans/transports | Exclude from this bounded branch | Published diagrams and live flow are already available. No need to import unrelated local work to prepare these two items. |

The preserved expanded draft SHA-256 was
`d4fa587ac6effe763300f78f3684c39cebb0c1ab2cc25f876d0e26df333f266b`.
The branch copy clarifies attribution and replaces unavailable local links.
Its source draft remains unchanged. See [the warm method and measurements](cost100-full-warm-audit.md).

## Publication state and next approval

A read-only check of the live `/api/memo` returned `claims_checked_provisional`
and the old ambiguous wording. Its text SHA-256 was
`65867d05665d63ebc34878e692f86b501e96915dd49685f59d39569ff27babe1`.
The site has not received this branch. The API uses the tracked fallback memo
for this status; publication must verify the served text after deployment.
Do not assume that changing Git also rewrites a stored database memo.

The frozen grading ZIP's memo is also unchanged. The grouping handoff now says
its byte-equality claim applied at the original handoff; the revised tracked
memo has different prose and the same 164 numeric claim lines. A future release
correction requires separate approval and new provenance. Never overwrite the
old release silently or change data to clear checker flags.

Remaining gates: publication approval, the older production-score provenance
conflict, private-input reproduction of the warm audit, absent historical
main checkpoints and verifier trail, and the existing `review_required`
grading result. Cost-scope and deadline discrepancies remain with their owners.
No paid call, push, merge, deployment, public upload, or submission occurred.

## Checks and exact file list

- `python3 -m unittest discover -s tests -t . -q`: **413 tests, OK, 2 skipped**,
  in **16.488 seconds** in the review worktree. The two skips require private
  golden-plan files. This run initially stalled reading an unchanged test file,
  then completed successfully. During the stall, a byte-matched candidate copy
  under the same Mac's temporary directory also passed **413 tests, 2 skipped**
  in **21.620 seconds**. Both results were received; no incomplete attempt is
  counted as a pass.
- `python3 -m spotify_pipeline --help`: passed.
- `node --test web/tests/privacy.test.ts`: one test passed.
- `node --check dashboard/static/app.js`: passed. No frontend dependencies
  were installed; a full Astro build/typecheck was not run for these text edits.
- Full warm audit: all six stages passed; 98 completed / 2 quarantined,
  254 outputs / 112 calls unchanged, zero paid/transport/socket attempts,
  original database unchanged. New private files are mode 0600 and ignored.
- Both tracked memo copies are identical. Their 164 claim lines match main
  exactly. The expanded memo's five public rows, shares, 30,377 denominator,
  and 91,754 severity total match the existing release.
- Candidate Markdown links, private-path/credential marker scan, and
  file-specific `git diff --check` passed. Aggregate report schemas were checked.
- The original expanded memo and audit tool retain their source hashes.
  The copied 13 October warm aggregate is byte-identical to its preserved original.

Exact changed/new file list (23 files; no raw data or private answers):

```text
README.md
dashboard/provisional_memo.md
dashboard/static/app.js
docs/assets/production-2026-10-12/MANIFEST.md
docs/tasks.md
reports/cost100-full-warm-audit-2026-10-13.json
reports/cost100-full-warm-audit-2026-10-15.json
reports/cost100-full-warm-audit.md
reports/evaluation-attribution-and-inclusion-2026-10-15.md
reports/free-verification-boundaries-2026-10-12.md
reports/grouping-v4-handoff.md
reports/issue-grouping-independent40-score.md
reports/issue-map-blocker-triage-2026-10-12.md
reports/issue-map-independent-validation-2026-10-12.md
reports/product-decision-memo-2026-10-13.md
reports/provisional-product-priority-memo.md
reports/rubric-assessment-2026-10-16.md
reports/rubric-benchmark-2026-10-13.md
reports/submission-status-2026-10-12.md
tools/audit_cost100_full_warm.py
tools/export_grouping_v4.py
web/src/components/dashboard/memo-panel.tsx
web/src/lib/reflections.ts
```
