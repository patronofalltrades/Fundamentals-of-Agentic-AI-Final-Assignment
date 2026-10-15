# Final submission checklist — verified 15 October 2026

## Submission cutoff and destination

Use **20 October 2026, 11:59 pm Pacific Time**. The
[current assignment document](https://docs.google.com/document/d/1PUFw56OGxqbUxiFm0vKtsWX8ac8633BgOlCSGa3TgLA/edit)
was read again on 15 October and explicitly extends the deadline to 20 October.
The coordinating task also checked the
[11 October course announcement](https://bcourses.berkeley.edu/courses/1555592/announcements/7376947),
which corroborates 20 October. The earlier user-reported 21 October date has no
newer supporting notice in the checked evidence. It is not an equally supported
deadline. Only a newer instructor notice should move this cutoff.

The single submission is the public repository URL through the final-assignment
portal linked in bCourses:

**https://github.com/patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment**

Hanif must make the submission and retain its receipt. No submission was made
by this closeout. No push, PR, merge, manual deployment, new inference, or paid
call is authorized for this branch.

## Current published state

- PR #30 merged at `44928e1` on 15 October. The attribution correction, expanded
  decision memo, and full warm-audit method/results are published on GitHub.
- PR #31 merged at **`2a725dcc3aca6f5882142c106141629274065cd9`**. It corrected
  cost scopes and historical architecture wording. Its automatic Production
  deployment reached `success` at 17:17:15 UTC. No deployment was triggered here.
- The [live dashboard](https://hanif-spotify-insights.vercel.app/) serves 110,000
  selected and 100,229 accepted rows. The [live memo](https://hanif-spotify-insights.vercel.app/memo/)
  retains the short provisional memo. Its API now names the assistant manual
  comparison, rejects a production-model accuracy interpretation, and retains
  all 164 claim lines. The expanded decision memo remains a separate GitHub report.
- The frozen grading release is unchanged. This local branch adds closeout
  reports and current assessment edits; those additions still need review and
  publication approval before a grader can rely on their GitHub links.

## Ten-criterion evidence gates

These are evidence states, not awarded grades. See the
[updated assessment](rubric-assessment-2026-10-16.md) for the argument and
[local handoff](submission-closeout-handoff-2026-10-15.md) for checks and file scope.

| Criterion | Current evidence state | Exact evidence / acceptance gate | Remaining action |
| --- | --- | --- | --- |
| D1 — Accessible code/setup/artifacts | Evidenced | [README](../README.md), [release](https://github.com/patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment/releases/tag/grading-2026-10-13), [cost setup](../cost/README.md), [architecture](../docs/architecture.md) | Approve/publish this local closeout and confirm repository/release/live URLs while signed out. |
| D2 — Architecture/schema/provenance | Partly evidenced | [Extraction](../docs/pipeline-extraction.mmd), [analysis](../docs/pipeline-analysis.mmd), [schema](../spotify_pipeline/contract.py), [grouping provenance](grouping-score-provenance-2026-10-15.md) | Keep missing provider/phase/cache-origin history explicit; accept only authentic recovered evidence. |
| D3 — Correct memo calculations/source evidence | Partly evidenced | [Claim memo](provisional-product-priority-memo.md), release `claims.csv`, `membership.csv`, `ranking.csv`; unchanged checker reproduces arithmetic | Semantic source support is not proven by exact quotes or arithmetic. Detailed source trace stays private. |
| D4 — Recommendation/alternatives/limits | Evidenced | [Expanded decision memo](product-decision-memo-2026-10-13.md): ads discovery, playback alternative, effort hypotheses, guardrails, stop conditions | Preserve its provisional recommendation and separate baseline/public numbers. Inclusion is already complete on main. |
| T1 — Fifty labels/comparisons/errors | Partly evidenced | [Golden diagnostic](golden-gap-and-checker-2026-10-12.md), live evaluation; 50 predictions, 26/38/30/14 exact matches by topic/intent/severity/joint | Quote/entity semantic scoring and needs-review quality remain incomplete. Keep overlap, uncertainty, and prior-influence limits. Human20 is optional follow-up, not a replacement for the original 50. |
| T2 — Independent/planted/injection checks | Partly evidenced | [Boundary tests](free-verification-boundaries-2026-10-12.md), archived model-verifier aggregate, [provenance distinction](grouping-score-provenance-2026-10-15.md) | Missing per-case verifier trail and real behavioral outcomes remain missing. No new run is authorized. |
| T3 — Cold/warm/calculator/controls | Partly evidenced | [Pilot](cost100-pilot.md), [calculator](../cost/README.md), [published full warm audit](cost100-full-warm-audit.md) | Warm inclusion gap is closed. Full repeat still requires private `pilot.db`; pilot/synthetic recovery does not establish historical main-run recovery or complete project billing. |
| W1 — Ingestion/coverage/classification | Partly evidenced | [Full profile](contract-ingestion.json), 100,229 accepted of 110,000 selected, [fresh checker](grading-closeout-2026-10-15.md) | Ask how the 100k allowance interacts with the unchanged full-corpus formula. Do not claim all 660,622 IDs were processed. |
| W2 — Bounded stages/handoffs/resume | Partly evidenced | [Pilot harness](../tools/cost100_harness.py), [queue](../spotify_pipeline/checkpoint5000_queue.py), pilot checkpoints, release synthetic video | Historical main-run checkpoints/phases absent. Large grouping was a chat-agent handoff. All 76,523 Jev calls sent one review, below the requested ten-review payload. |
| W3 — Ranking/database/backend/dashboard | Evidenced | Live dashboard/API, 41 reproduced ranks, 164 claims, saved database-backed results | Recheck live read-only routes before submission; keep advisory product-quality limits. |

## Exact package and URL checks

| Gate | Result at this closeout | Required before submission |
| --- | --- | --- |
| Repository main | PRs #30/#31 merged; current base `2a725dc` | Confirm intended final commit and include only reviewed subsequent changes. |
| Dashboard and memo | Live API counts and corrected attribution verified | Open both URLs signed out; do not expose private review/answer files. |
| Expanded memo / full warm evidence | Both present on merged main | Keep their relative README links valid; do not call them local-only. |
| `grading-110k.zip` | SHA-256 `a596dae7c47c61b864e03e374e6165b443222fc736e0c741c6e03d5db68d9198`; all 12 members equal the candidate | Download via the [release](https://github.com/patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment/releases/tag/grading-2026-10-13); verify `SHA256SUMS.txt`. |
| Required grading files | `run.json`, `ingestion.json`, `records.jsonl.gz`, `membership.csv`, `ranking.csv`, `claims.csv`, `calls.jsonl` present | Keep all selected IDs and genuine unresolved states. |
| Missing required checkpoint pair | `checkpoint_before.json` and `checkpoint_after.json` absent for main run | Disclose; do not substitute pilot or synthetic snapshots. |
| Official checker | Rerun remains `review_required`; [reproduction](grading-closeout-2026-10-15.md) | Keep its full report private; publish only reviewed aggregates. No rule weakening. |
| Frozen ZIP memo vs current memo | Old release prose remains; 164 claim lines unchanged | Decide whether to publish a clearly versioned release addendum. Current README and memo already correct attribution. |
| Cost scope | Exact ledger/export reconciliation complete | Preserve [three-stage breakdown](cost-scope-reconciliation-2026-10-15.md); unknown charges and grouping usage stay unknown. Ask cost owner to qualify historical evidence maximum 50 versus scale maximum 25. |
| Deadline | 20 October, 23:59 Pacific supported by current course sources | Submit by that cutoff unless a newer instructor notice is supplied. |
| Portal receipt | Not submitted | Hanif submits the repository URL and saves the receipt. |

## Human20: exact next action if a fresh diagnostic is chosen

The original 50-case evaluation is complete; the rubric does not require a new
20-case set. A fresh set is useful only for a separately declared evaluation
after answer-influenced changes or for missing semantic measures. It does not
erase the original diagnostic's limits.

The existing private packet has 20 selected cases. The expected
`human20_completed.csv` was absent at this check. Spreadsheet/Numbers answer
completion was not inspected, so this does not mean the workbooks are blank.

1. Hanif opens the existing private `prospective_human20_20261013` packet and
   reads `HUMAN_INSTRUCTIONS.md`. Use an existing completed human workbook if
   one exists; do not relabel completed work blindly.
2. Preserve the six source columns. Complete only the eight `human_` columns
   for all 20 cases. Do not consult model predictions, old golden answers, or
   rankings while labeling. Mark ambiguity and supply the requested rationale.
3. Export `human20_completed.csv` beside the instructions, retaining the original
   blank. Return only its local path and confirmation of completion to the
   coordinator; do not paste answers or review text into chat.
4. Separately approve any needed source-only model predictions and a frozen
   evaluation protocol before scoring. An isolated scorer must verify all 20
   source identities and emit aggregates only. No new inference or scoring is
   included in this closeout.

## Closed, disclosed, and approval-dependent

**Closed:** merge/production verification; assistant-versus-agent score artifact
distinction; exact cost reconciliation; current publication attribution; fresh
unchanged checker run; release/candidate hash equality; supported deadline and
this ten-criterion evidence map.

**Disclosed, not repaired:** full-corpus shortfall; incomplete selected rows;
split provenance, unknown phases/usage and absent historical checkpoints;
one-review Jev payloads; incomplete semantic/behavioral evaluation; private-input
warm reproduction; the frozen release's earlier memo prose.

**Needs a decision:** publication of this local branch; whether to add a versioned
release note; instructor grading-scope clarification; optional human20 work;
and whether to authorize a bounded code-only source-emptiness check before any
one-row status-format adapter. Automatic approval review blocked that proposed
direct text check under the current no-review-text boundary; no record changed.
