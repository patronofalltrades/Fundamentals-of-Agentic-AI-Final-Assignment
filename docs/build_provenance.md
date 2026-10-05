# Build provenance

- Selected coding model: `opencode-go/deepseek-v4-flash-vision-exp`.
- DeepSeek ran through OpenCode CLI in two coding passes.
- Its tool access was limited to project file reads and edits. Shell, web,
  external-directory, and other-agent tools were denied.
- This is a local development branch and is not yet published.
- Coding requests used the selected Go route. They are separate from future
  runtime classification requests. No paid fallback or provider substitution
  was enabled.
- No model or provider classification calls were made. No provider is selected
  for the corpus classifier yet.
- The coding sessions received requirements, code, and synthetic fixtures.
  They did not receive source CSVs, credentials, or golden answer labels.
- Codex made targeted review fixes and ran 134 synthetic tests successfully.
- Codex ran actual offline ingestion locally. The full core profile matches
  the supplied course helper exactly. See `../reports/ingestion-checks.json`.
- The source and original golden files were preserved. Zero runtime
  classifications or classification calls occurred.
- The implementation is local and awaiting review. No push was made.

The cost artifacts remain intentionally incomplete: measurements are
`not_measured`, rates carry null prices with unknown dated source, output and
fallback caps are unset, and no projection or scaling is approved. This is not
a completed pilot and claims no model output, evaluation or cost. The admission
helper is an offline check only; unset caps block admission and no human
approval is recorded.

## Review-fix pass

A second file-only pass addressed defects found after the controlling agent
  ran the first suite. It added regression tests for the real manifest layout,
strict CSV decoding, authoritative source identity, cache/quarantine
immutability, streaming state copy, safe publication ordering and honest cost
scaffold status. That coding pass had no dataset, shell, or web-tool access.
Final Codex checks corrected numeric synthetic wall-time fixtures, rejected
unknown cache settings, kept configuration counts separate, and checked
billing-unit consistency. These changes did not add provider adapters.
