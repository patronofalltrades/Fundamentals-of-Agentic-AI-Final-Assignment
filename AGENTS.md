# AGENTS.md — Concurrent work contract

This repository is worked on **concurrently by three AI agents**, coordinated by Hanif. This file is the shared contract: who owns what, how we avoid colliding, and what handoffs each agent must provide. Read it before doing anything.

## Project

Final Assignment — Multi Agent Large Data Processing Pipeline. Turn 660,622 historical Spotify reviews into a grounded product recommendation. **Deadline: Oct 13, 2026 11:59pm PT.** Submission = this public repo.

Key facts: 660,609 nonempty reviews to classify, 13 empty texts to quarantine (`empty_review_text`), 484,189 distinct nonempty exact texts (exact-text cache reuse allowed), full-file SHA-256 `1fc85de68a304dd8978b537cfa58793d5f41cbaf417fa32cb53899f83a2fcef6`.

## Roles (no overlap)

| Agent | Role | Owns | Must NOT do |
|---|---|---|---|
| **Claude Opus** | Infrastructure | `src/` (except `src/labelling/`), `cost/` calculator, `grading/` exporter, repo hygiene, `docs/INTERFACES.md`, vendored `check_submission.py` | No model calls / no API spend / no labelling / no evals |
| **OpenCode** | Labelling | `src/labelling/model_client.py`, all enrichment runs (`cost_100` → `checkpoint_500` → `analysis_10000` → full corpus), `records.jsonl` + `calls.jsonl` data | No infra design, no golden labels, no eval analysis |
| **ChatGPT** | Evals | `evals/` (golden-50 labels, verifier role, error analysis, overlap disclosure, adversarial tests) | No infra, no production labelling runs |

Infra provides contracts; labelling fills the model client; evals consumes records and reports back. Each agent documents the interfaces it needs in `docs/INTERFACES.md` (kept by Claude Opus).

## Source of truth

- Specs are authoritative and live in `docs/specs/` (vendored from the course dataset by Claude Opus): `GRADING_CONTRACT.md`, `COST_CALCULATOR.md`, `manifest.json`, dataset `README.md`.
- The zero-API grader `check_submission.py` is vendored at repo root. Its expectations define the grading export formats.
- Raw CSVs are **not committed** to the repo. The full dataset lives locally at `~/Desktop/Fundamentals of Agentic AI - Final Assignment - Spotify/Final Assignment - Spotify Reviews Dataset/`. All agents use that path for runs; grading evidence is committed in `grading/` (JSONL may be gzipped).

## Branch strategy (avoid conflicts)

- `main` — stable, review-only. Do not push directly.
- `claude-infra` — Claude Opus.
- `opencode-labelling` — OpenCode.
- `chatgpt-evals` — ChatGPT.

Work on your branch, commit atomically with clear messages, push so others can see your interfaces early. Merging is coordinated by Hanif. If you must touch a file owned by another agent, open a short note/issue instead of editing directly.

## Directory layout & ownership

```
docs/                 Claude Opus   specs, INTERFACES.md, architecture, agent briefs
src/                  Claude Opus   pipeline modules (prepare, state, spend, enrich, verify, group, rank, claims, memo, grading)
src/labelling/        OpenCode      model_client.py (interface from Claude, impl by OpenCode)
evals/                ChatGPT       golden labels, verifier, error analysis, adversarial tests
grading/              Claude Opus   exporter; OpenCode produces records/calls data into it
cost/                 Claude Opus   calculator + pilot measurements (OpenCode supplies pilot call logs)
```

## Handoffs (produce early, they unblock others)

1. Claude Opus → OpenCode: `model_client.py` interface + `run_labelling.py` CLI + mock client (dry-run, no keys). OpenCode implements the real client against it.
2. Claude Opus → ChatGPT: verifier interface + golden-label ingest format + `check_submission.py` reference/check command.
3. OpenCode → Claude Opus: real `pilot_calls.jsonl` + usage so the cost calculator gets measured data.
4. OpenCode → ChatGPT: completed `records.jsonl` so evals can compute agreement.
5. ChatGPT → all: golden labels and eval reports; overlap disclosure (6 golden rows / 5 distinct texts overlap the dev sample).

## Cross-cutting rules

- **Money:** no paid calls without explicit budget approval. Everything must run offline with `.env.example` blank credentials. Opening the cost calculator must never trigger paid calls.
- **Batch limit:** enrichment requests carry at most 50 reviews; validate every returned ID; save after each batch.
- **Caching:** exact-text reuse must set `cache_source_id` pointing directly to a completed original with identical text, identical label fields, and identical `label_config`. No cache chains.
- **Checkpointing:** atomic saves; resume must not re-call completed IDs under unchanged config.
- **Stars are metadata:** rating must not substitute for text-based intent/severity.
- **Golden labels** never enter prompts, examples, caches, or routing thresholds.

## Definition of done per stage

- `cost_100` pilot (cold + warm): real measurements, failures accounted, offline replay works.
- `checkpoint_500`: labels evaluated, interruption/resume demonstrated, cost estimates refreshed.
- `analysis_10000`: quality/cache/retry/throughput/cost assumptions refreshed; scaling decision documented.
- Full corpus: all IDs accounted, 13 quarantined, ranking + memo grounded, `check_submission.py` passes.
