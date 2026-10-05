# Coding model price reference

Current choice: **DeepSeek V4 Flash 0731**, **OpenRouter**, **OpenCode CLI**.
Verified local ID: `openrouter/deepseek/deepseek-v4-flash-0731`.

Observed October 5, 2026. USD per 1,000,000 tokens.
Source: https://openrouter.ai/deepseek/deepseek-v4-flash-0731

| Upstream provider | Uncached input | Output | Cache read |
| --- | ---: | ---: | ---: |
| Relace | 0.0152 | 1.28 | 0.0152 |
| DeepInfra | 0.06 | 0.18 | 0.015 |
| Together | 0.14 | 0.28 | 0.03 |

These are selected provider quotes, not an exhaustive table. The page headline
reflects Relace and is not a universal rate. No actual OpenRouter request route,
usage, or charge was measured. The project configuration selects OpenRouter
but does not pin an upstream provider. Do not use an arbitrary row as an
actual cost. Verify routing, fallback, dated prices, usage, charges and potential
spend before further inference. Keep coding and runtime costs separate.
The strictly below US$50 cap applies; no top-up or credential change is authorized.
`cost/rates.json` remains null because the runtime route is undecided.
