# Earlier pilot attempts (kept as evidence, not part of the measured pilot)

The measured pilot is `../pilot_calls.jsonl` (cold `runs/pilot-cold`, warm `runs/pilot-warm`, 2026-10-05 23:13–23:15 UTC).
Two earlier live attempts failed or were incomplete. They are kept here because the assignment asks for all
attempted calls, failures included. Their spend is real and is listed below; the calculator's measured bill
covers only the final cold/warm pair.

| Attempt | What happened | Calls | API cost (rates.csv) | Fix |
|---|---|---|---|---|
| `pilot-cold-attempt1-failed` | TypeSafe returned `HTTP 503: no healthy upstream` on 14 of 15 Jev attempts; 72 reviews were quarantined `retries_exhausted`, 28 completed. Every verify/group/memo call failed with a local `TypeError` (anthropic SDK 1.x no longer accepts `temperature=`), so no Anthropic request was sent. | 15 enrich (1 succeeded), 6 chat (0 sent) | $0.001074 (Jev, 25,563 input tokens) | Backoff raised to 8 attempts / 2 s base (commit ff41bf1); `temperature` moved to `extra_body` (ff41bf1). |
| `pilot-warm-attempt1-stage-cache-miss` | Warm run made 0 enrichment calls, but re-called verify, group and memo because the stage result cache was never given the cold run directory. | 3 chat | $0.023606 (Haiku 4.5) | `warm_from` passed to the stage context + regression test (065a3b9). |

Other spend on 2026-10-06: one adapter check call to Claude Haiku 4.5 (53 input / 14 output tokens, about $0.0001).
Token-counting calls used to validate the API key are free.

**Total API spend for pilot work: about $0.052** (measured pilot $0.027132 + attempts $0.024680 + check $0.0001).

## Superseded: extract-v1 pilot (`pilot-extract-v1-superseded/`)

The first clean pilot (cold $0.027132 / 35.7 s, warm 0 calls / 0.95 s) used `extract-v1`, whose substring
entity matching tagged "bad app" reviews as `ads` (8 of 15 `ads` tags were false). After the whole-word fix
(`extract-v2`, branch `fix/labelling-entity-boundaries`, reviewed and merged by OpenCode as 9a304ca), the pilot
was re-run with `label_config = typesafe/jev-latest:prompt-v1:extract-v2:schema-a5-v1`. The measured pilot in
`../pilot_calls.jsonl` is the extract-v2 run (cold $0.027741 / 34.8 s; warm 0 calls / 0.81 s).

**Run-to-run variation (measured, same 100 reviews, same Jev settings, two cold runs):** intent and severity
identical on 100/100; topic differed on 3/100; needs_review on 2/100; sentiment differed (small float changes)
on 59/100. Jev is therefore close to, but not exactly, deterministic. The exact-text result cache is what
makes reruns reproducible; a fresh cold run can move a few labels and reorder close-ranked issues.

Updated total API spend for pilot work: about $0.08 (extract-v2 pilot $0.027741 + superseded extract-v1
pilot $0.027132 + failed attempts $0.024680 + adapter check $0.0001).
