# Product decision: investigate ad interruption first, retain playback as the alternative

**13 October 2026 · provisional recommendation · historical Google Play reviews**

Prepared for inclusion on 15 October from the preserved local draft. Aggregate
claims were checked against the existing release; attribution and links were
clarified. Publication and replacement of the deployed memo await approval.

## Decision and customer problem

Allocate the next discovery effort to **ad frequency or interruption (`USE-ADS`)**. Keep **playback fails or stops (`PLY-FAIL`)** as the comparison and the next candidate for delivery. Do not approve an ad-policy change from this ranking alone.

The intended user is a listener who wants to start or continue chosen audio without an unexpected interruption. The saved map suggests two different problems: interruption associated with ads, and failure of playback itself. They require different remedies. The records do not establish the listener's subscription, device, current app version, or underlying technical cause for every case.

This decision identifies where to gather stronger evidence next. Churn, revenue, affected customers, and feature value remain unmeasured. Reviews were written in the historical source window and do not represent all current Spotify users. The [full-source ingestion report](contract-ingestion.json) and the [accepted-evidence report](accepted-100k-completion.md) describe the source and selected run.

## What the saved evidence supports

The source has 660,622 review IDs. The selected run contains 110,000 IDs and 100,229 structurally accepted rows. Among accepted rows, the corrected issue map contains 30,400 complaint or cancellation records, with one issue per record. The public projection excludes 23 known flagged members, leaving **30,377**. It contains **28,720 complaint** and **1,657 cancellation** labels. A cancellation label is a statement in a review, not an observed account cancellation.

The following table uses the public projection throughout. `severity_sum` is the sum of saved severity labels. Means use six decimal places and half-up rounding. The order is severity sum descending, then issue ID ascending. Counts and severity sums were recomputed from the same joined rows used by the backend, not inferred from separate marginal totals.

| Public rank | Issue | Records | Severity sum | Mean severity | Share of 30,377 |
| --- | --- | ---: | ---: | ---: | ---: |
| 1 | `USE-ADS` — Ad frequency or interruption | 5,195 | 11,869 | 2.284697 | 17.10% |
| 2 | `PLY-FAIL` — Playback fails or stops | 2,474 | 8,904 | 3.599030 | 8.14% |
| 3 | `GEN-GENERAL` — General or unspecified criticism | 3,646 | 7,831 | 2.147833 | 12.00% |
| 4 | `PLY-SELECTION` — Wrong audio plays | 2,015 | 6,671 | 3.310670 | 6.63% |
| 5 | `PLY-QUALITY` — Audio, loading, or connection quality | 1,646 | 5,315 | 3.229040 | 5.42% |

Source: the [published grading release](https://github.com/patronofalltrades/Fundamentals-of-Agentic-AI-Final-Assignment/releases/tag/grading-2026-10-13), its `ranking_public.csv`, and the [live aggregate flow](https://hanif-spotify-insights.vercel.app/api/flow). The [backend flow calculation](../dashboard/server.py) joins accepted records to membership and excludes known flags. The public severity total is **91,754** across all 41 issues. These sums are ordinal prioritization scores, not measured customer harm in a physical unit.

[Explore the published complaint flow](https://hanif-spotify-insights.vercel.app/#issues).

The flow shows saved intent, saved broad topic, and mapped issue. Broad topics and issue families are separate labels. Their crossovers are retained, not forced to agree. The issue column displays the five leading issues by severity sum and combines the other 36 for legibility. Width encodes record count, so it does not reproduce the severity ranking visually.

### Why ads lead this decision

Ads have the largest saved issue-level severity sum and over twice the mapped record count of playback failure. This gives ad interruption a useful combination of recurrence and aggregate severity for discovery. Its public score exceeds playback failure by **2,965**. That difference is arithmetic, not a confidence interval or proof of a stable ordering after human relabeling.

Playback failure has fewer mapped records but a higher mean severity. It directly threatens the core listening task. It remains a strong delivery alternative if human review finds the ad group combines expected free-tier behavior, unrelated complaints, and actual defects. General criticism is frequent, but its broad wording gives less direction for a specific intervention. Wrong audio and audio/connection quality deserve distinct diagnostics rather than being folded into an ad experiment.

### Baseline and public values must stay separate

The course baseline includes flagged members. Its leading issue has **5,197 records and severity sum 11,874**. These are the existing saved claims `claim-0001-complaint_count` and `claim-0001-severity_sum`. Playback failure is **2,474 and 8,904** in both views, with `claim-0002-complaint_count` and `claim-0002-severity_sum`. The [original provisional memo](provisional-product-priority-memo.md) holds the 164 checked baseline claim references. This expanded memo adds aggregate interpretation; it does not replace that saved claim ledger or the deployed memo.

## Alternatives and tradeoffs

Effort and value below are hypotheses. The project has no engineering estimates, experiment telemetry, or unit economics for these options.

| Option | Expected customer value | Confidence from this project | Effort and risk | Decision |
| --- | --- | --- | --- | --- |
| Review a new sample of ad and playback cases; reproduce reported journeys | Separates actionable interruption defects from expected behavior and label errors | Strong reason to investigate; weak evidence for any specific fix | Bounded discovery effort; reversible; needs fresh cases and human review | **Start here** |
| Fix one verified ad-transition or restart defect | May let a listener resume intended audio reliably after an ad | Unproven until a defect is reproduced | Depends on client/ad-stack diagnosis; could affect ad delivery | First-release candidate after the review |
| Prioritize playback failure reliability | May restore the core listening task for more severe failures | Higher mean saved severity; still exposed to mapping error | Cause may involve network, device, backend, or client state | Keep as explicit competing priority |
| Reduce ad frequency broadly | Could reduce perceived interruption | Reviews do not estimate an optimal ad load or causal retention effect | Product and revenue tradeoffs are unmeasured; difficult to justify from counts | Defer pending experiment design and business review |
| Build a broad usability redesign | Could address several recurring frustrations | Saved broad topics combine many distinct tasks | Large scope makes attribution and learning harder | Defer; choose a specific journey first |

## Proposed discovery and first release

**Hypothesis:** We believe that fixing a confirmed interruption in the ad-to-audio transition will help affected listeners continue their chosen audio, measured by a higher successful-resume rate after an ad. This hypothesis is not a finding from the review corpus.

1. Draw a fresh, source-matched review sample from the ad and playback groups. Declare the sampling method before judging cases. Include both complaint and cancellation labels. Do not reuse the 91 overridden grouping cases or the golden 50 as an untouched test set.
2. Have human reviewers independently distinguish ad frequency dissatisfaction, an ad-transition defect, a premium-entitlement claim, a playback failure, and insufficient detail. Freeze decisions before comparing model labels. These are proposed review questions; they do not silently change the frozen 41-issue catalog.
3. Reproduce any supported failure on an identified app version and listening journey. Record device, network, entitlement, ad transition, and resume behavior. Use product telemetry to estimate exposure if available.
4. If one defect is reproducible and its fix is narrow, release that fix to an eligible test cohort. If the ad group has little actionable support, compare the verified playback failures and change the priority explicitly.

The first release should let an affected listener start chosen audio, pass an ad break, and return to the intended audio without a forced restart. Scope should follow the reproduced defect. It should not promise fewer ads, a new subscription policy, or a broad redesign.

### Success and stopping signals

- **Outcome:** successful audio resume after an ad among eligible affected sessions. The baseline and target are unknown; measure and agree them before launch.
- **Supporting signals:** time to resume, repeated play attempts, and recurrence of the reproduced failure.
- **Guardrails:** playback crash rate, unintended playback, ad completion behavior, and entitlement errors. Business owners must select any commercial guardrails from real telemetry.
- **Decision point:** review human agreement and reproducibility before building; review the outcome and guardrails after the bounded experiment. Stop or revise if the issue cannot be reproduced, the measured failure is rare in the intended cohort, or guardrails worsen.

## Why this extraction and analysis design was used

The implemented classifier uses Jev `jev-1.13.0` for constrained topic, intent, severity, and sentiment labels. Its current request builder sends **one review per request**. The durable mixed queue calls that builder for one row at a time. Worker concurrency is distinct from payload size. Earlier README wording about ten reviews per Jev request was not supported by this code.

The evidence stage uses OpenRouter `openai/gpt-oss-120b` on the pinned DeepInfra route. The adopted configuration sends up to **25 distinct review texts per request**, with a smaller tail when needed. It requests entities and a verbatim supporting quote. Code checks returned IDs, response shape, finish reason, exact source membership, route, token bounds, and usage. Invalid evidence is quarantined; uncertain provider outcomes retain their cost reservations. These checks support traceability and spending control. They cannot establish that a quote semantically proves the chosen label.

Exact-text caches reduce repeated inference while preserving a separate validated result for each source ID. Configuration identity includes model, effort, prompt, and schema. Queue state and budget reservations are durable. The published [extraction diagram](../docs/pipeline-extraction.mmd) and [analysis diagram](../docs/pipeline-analysis.mmd) show those controls and their evidence limits.

The large issue map came from a separate historical Claude Code agent handoff. The README attributes the grouping to eight Claude Sonnet 5.5 agents and the verifier to Claude Opus 5.5. This memo preserves that reported attribution; missing per-call artifacts prevent independent reconstruction of all model identities, inputs, usage, and costs. Code applied reviewed corrections and 91 human overrides, validated one membership per candidate, and computed the final ranks. The separate 100-review harness implements all roles as saved program stages; that does not retroactively make the large grouping handoff a program stage.

The measured pilot and [offline cost calculator](../cost/README.md) inform cost planning. This memo does not infer model superiority from low cost or structural acceptance. No new inference or spending was used to write it.

## Confidence and limitations

- **Label evaluation:** all 50 frozen source-only predictions exist. Topic agreement is 26/50, intent 38/50, severity 30/50, and joint agreement 14/50. Severity MAE is 0.56 and sentiment MAE 0.21. Twelve human rows ask for review; eight source texts overlap development data. Earlier golden influence is unknown. These are diagnostic results, not population accuracy.
- **Grouping evaluation:** the [16/40 comparison](issue-grouping-independent40-score.md) measures agreement between one assistant's manual assignments and human answers. It did not evaluate the production grouping model. Aggregate human family counts were visible before those predictions were frozen. The sample has five cases per broad topic, not population proportions. The historical handoff also reports 511/600 model-verifier agreement; inspected case-level verifier evidence is missing. Neither figure is an unbiased estimate of production mapping accuracy. Older reports claim a separate agent-label score with the same exact total but a different family total; the [attribution audit](evaluation-attribution-and-inclusion-2026-10-15.md) preserves that unresolved provenance separately.
- **Human overrides:** 51 pilot cases and 40 comparison cases were incorporated into final membership. They are no longer untouched grouping holdouts.
- **Known flags:** 47 accepted records are blocked from representative examples; 23 of them are ranking candidates excluded from this public flow. Removing known flags does not prove the remaining records correct.
- **Taxonomy:** catalog boundaries remain unresolved for several reported experiences, including premium-ad claims, free-tier limits, and app installation. The project has no adjudicated prevalence estimate for those gaps.
- **Coverage:** accepted rows are a selected historical cohort, not all 660,622 IDs or all current users. Exact-text aliases remain distinct source records. One issue per record can omit secondary concerns.
- **Provenance:** the unchanged grading checker remains `review_required`, with full-corpus scope, call-history, cache-origin, and checkpoint gaps. No diagram or prose revision removes those gaps.

## Recommendation to the product reviewer

Approve a bounded human review and reproduction effort focused on ad interruption, with playback failure as the explicit alternative. Approve delivery only after the evidence identifies a concrete journey and a measurable failure. This preserves the strongest observed signal while keeping the decision reversible when better evidence arrives.
