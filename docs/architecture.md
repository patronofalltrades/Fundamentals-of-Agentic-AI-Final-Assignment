# Agent collaboration and planned runtime

The two groups have different jobs. Development agents help build and review
the code. The runtime part below is the original plan, written before the main
run. For what actually ran, see `docs/pipeline-extraction.mmd` and
`docs/pipeline-analysis.mmd` (also drawn on the dashboard's Pipeline section).

```mermaid
flowchart TB
    subgraph DEV[Development collaboration]
        Hanif[Hanif: decisions and approvals]
        Alfred[Alfred - OpenAI Dots: plan and review]
        CLI[OpenCode CLI: selected coding route]
        DeepSeek[DeepSeek V4 Flash 0731 via OpenRouter: code]
        Sol[Sol - ChatGPT: occasional reasoning and review]
        Golden[Human-only golden answer labels]
        Hanif --> Alfred
        Alfred --> CLI
        CLI --> DeepSeek
        DeepSeek --> Alfred
        Alfred -.-> Sol
        Sol -.-> Alfred
        Hanif --> Golden
    end

    subgraph RUN[Planned runtime: original design]
        Python[Python orchestration]
        Prepare[Code: prepare, hash and deduplicate]
        Classify[Classifier TBD: at most 50 reviews per request]
        Verify[Opus candidate: small independent sample, blind to first labels]
        Compare[Code: compare predictions and save disagreements]
        Group[Grouping role: model TBD, code saves accepted mapping]
        Rank[Code: rank by severity_sum, stable issue ID tie-break]
        Memo[Memo role: model TBD, bounded evidence]
        Human[Human: check claims and recommendation]
        Saved[Code-owned artifacts: records, calls, membership and claims]
        Controls[Code-owned validation, budget and checkpoints]
        Eval[Code: evaluate against isolated human answers]
        Python --> Prepare
        Prepare --> Classify
        Prepare -->|original text and rubric only| Verify
        Classify --> Compare
        Verify --> Compare
        Compare --> Group
        Group --> Rank
        Rank --> Memo
        Memo --> Human
        Python --> Controls
        Controls -.-> Classify
        Controls -.-> Verify
        Controls -.-> Group
        Controls -.-> Memo
        Classify --> Saved
        Compare --> Saved
        Group --> Saved
        Rank --> Saved
        Memo --> Saved
        Classify --> Eval
    end

    DeepSeek -.-> Python
    Alfred -.-> Human
    Golden --> Eval
```

Hanif makes decisions and supplies the golden answers. Alfred is OpenAI Dots
and coordinates the plan and review. DeepSeek V4 Flash 0731 uses OpenRouter
through OpenCode CLI for future code work.
The two past coding passes used OpenCode Go; see `build_provenance.md`.
Sol is ChatGPT and can help with occasional reasoning. Coding runs through
OpenCode CLI.

What ran differs from this plan in four ways:

- Jev labelled one review per request, and DeepInfra `openai/gpt-oss-120b` extracted evidence for up to 25
  reviews per request.
- Grouping ran as a chat handoff: eight Claude Sonnet 5.5 agents and a blind Claude Opus 5.5 verifier on 600
  cases. Their saved inputs and outputs were recovered on 16 October; their usage was not recorded.
- On 16 October, `tools/gap_closure_eval.py` added a recorded grouping stage, a blind verifier at ten reviews per
  request, planted-error and prompt-injection tests, and a real interruption and resume, all with saved calls.
- Code owns the live controls: the shared ledger with worst-case reservations and holds
  (`spotify_pipeline/project_budget.py`), the durable queue and checkpoints, ID and exact-quote validation,
  ranking and claim checks.

Golden answers flow only to code evaluation. They never enter model inputs.
The project ceiling is US$49.99. Paid execution needs approval.

This is a GitHub Mermaid diagram. It describes responsibilities and planned
handoffs. It does not prove execution, automatic coordination, or shared locks.
