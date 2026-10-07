# Agent collaboration and planned runtime

The two groups have different jobs. Development agents help build and review
the code. Runtime roles will process reviews after access, quality, and budget
checks. The offline foundation is under review. The runtime has not run.

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

    subgraph RUN[Planned runtime: not run]
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

Python will dispatch bounded tasks and save handoffs. The verifier will receive
original text and the rubric before it sees the classifier's prediction.
Grouping will produce a saved mapping. Code will calculate the ranking.
The memo role will receive saved aggregates and a small evidence pack.
A human will check the final argument.

Golden answers flow only to code evaluation. They never enter model inputs.
GLM is not selected. Opus remains a verifier candidate. Runtime access and pilot quality are pending.
The project ceiling is US$49.99. Paid execution still needs approval.
Saved state, validation, and budget controls are code responsibilities.
The live controls and full runtime remain unimplemented.

This is a GitHub Mermaid diagram. It describes responsibilities and planned
handoffs. It does not prove execution, automatic coordination, or shared locks.
