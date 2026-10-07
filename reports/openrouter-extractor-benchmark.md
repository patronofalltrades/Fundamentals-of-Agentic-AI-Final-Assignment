# Hosted evidence extractor benchmark: prepared, live run blocked

**Decision:** Do not start the 100,000-row inference run or resume the smoke
launcher yet. One hosted inference succeeded and the next has uncertain
delivery. The two-route comparison is incomplete. This workspace sandbox
cannot resolve OpenRouter's domain, so local public-catalog checks cannot
confirm the connected Mac's route availability.

**October 6 live preflight update:** Hanif's smoke command stopped on the
public catalog check before sending a review. The pinned DeepInfra 120B
entry then had `status: -5`; the requested Groq 20B entry had
`status: 0`. The endpoint tags and model IDs still match. The validator's
`status != 0` hold is operating as written; there is no demonstrated parser
bug and no basis to substitute another provider. A read-only ledger check
found **zero call rows, zero reservations, and zero charges at that time**.
A regression fixture checks this fail-closed status case.

**October 7 connection-loss update:** The ignored ledger now contains one
successful DeepInfra inference and one DeepInfra inference with uncertain
delivery after a `URLError`. The latter was reserved before dispatch, so
its POST may have reached OpenRouter and may have been billed. Known settled
usage charge is **$0.000014102**; the uncertain reservation is
**$0.024903544**; combined cap exposure is **$0.024917646**. No Groq
inference is recorded. The runner cannot identify a provider request ID for
the uncertain call. The supplied connection-reset traceback lacks its
preceding frames, but the ledger's `URLError` on an `uncertain` call places
the failure in the inference POST path. The workspace shell still cannot
resolve the public catalog domain; this separate sandbox DNS failure does
not establish the user's Mac connection state.

Public catalog GETs now retry at most three times for connection errors,
timeouts, or HTTP 502/503/504, with short delays. Other HTTP errors fail
immediately. Inference POSTs never retry automatically. A launch now stops
before any new call while the ledger contains an uncertain, invalid, or
in-flight inference. **Do not rerun the smoke launcher yet.** Hanif must
check OpenRouter activity/billing for the uncertain DeepInfra request around
the connection loss and share only the outcome and any charged usage, not
the key or review text. Reconcile the saved attempt before resuming. Privacy
compatibility and Groq behavior remain unmeasured.

### Reconcile the uncertain request

The local ledger has attempt **1** (DeepInfra 120B, succeeded) and attempt
**2** (DeepInfra 120B, uncertain after `URLError`). It saves elapsed durations
but **no UTC start or end timestamps**. The user's approximate connection-loss
time is October 7 around 01:16 UTC; do not present that as an exact call time.
The first attempt has a saved provider generation ID that can help bracket
activity. The uncertain attempt has **no saved provider request/generation ID**.
Do not put source review IDs, review text, or credentials in a shared report.

In OpenRouter activity, inspect DeepInfra `openai/gpt-oss-120b` requests near
that time. For the possible second request, record its UTC creation/completion
times, provider generation/request ID if present, outcome, prompt tokens,
completion tokens (including reasoning), reasoning-token breakdown if shown,
and billed USD amount. Say explicitly if there is no matching bill after
settlement. Do not infer no charge from a missing immediate dashboard entry.
The first request's saved usage is 156 input, 49 output including 18 reasoning
tokens, with a $0.000014102 usage-derived charge; that can help identify it.
Its response passed strict JSON, exact source-row hash, quote-substring, and
whole-boundary entity checks when saved and on read-only revalidation. This
is mechanical validity for one row, not evidence-quality or accuracy proof.
Keep attempt 2's full reservation and inference block until its billing and
delivery outcome is established and documented.

## Fixed comparison

The same manifest-verified `cost_100.csv` rows feed both routes. The frozen
Jev v2 labels supply topic, intent, severity, and sentiment. Saved Codex
exact-source evidence is a comparison baseline, **not human truth**. The
development set is not a clean unseen evaluation: six golden rows have five
exact texts also present in development data. Human golden answer columns
were not opened.

| Route | Endpoint tag | Input / output USD per million tokens | Listed features |
| --- | --- | ---: | --- |
| `openai/gpt-oss-120b` | `deepinfra/bf16` | 0.037 / 0.17 | structured outputs, response format, reasoning effort |
| `openai/gpt-oss-20b` | `groq` | 0.075 / 0.30 | structured outputs, response format, reasoning effort |

Prices and features were checked on October 6, 2026 against the [120B
endpoint listing](https://openrouter.ai/api/v1/models/openai/gpt-oss-120b/endpoints)
and [20B endpoint listing](https://openrouter.ai/api/v1/models/openai/gpt-oss-20b/endpoints).
The runner checks the exact tag, price, feature list, and endpoint status
again before paid work. [OpenRouter's structured output guidance](https://openrouter.ai/docs/guides/features/structured-outputs)
specifies strict JSON schema and `require_parameters`. Its [privacy guidance](https://openrouter.ai/docs/guides/get-started/sovereign-ai)
documents `data_collection: deny` and `zdr: true`. The request also pins
`provider.only` to one tag and sets `allow_fallbacks: false`. If those
safeguards cannot be honored by a route, the request must fail; no route or
policy is silently relaxed. Authenticated route/access remains unverified.
The public endpoint listings do not expose a per-endpoint ZDR field. They
therefore do **not** establish that either pinned route accepts ZDR. A live
request with `zdr: true` is the remaining compatibility check; if it fails,
stop instead of removing the safeguard.

## Controls and offline result

`tools/openrouter_extractor_benchmark.py` has an explicit execution command;
import and read-only reporting make no paid calls. It validates the supplied
source identity and each Jev label's source-row hash. It sends one review per
request, asks for strict JSON, uses low reasoning and a 320 completion-token
limit, then checks exact quote and whole-boundary entity spans. Output token
usage includes billed reasoning; the code does not add reasoning tokens to
the bill twice. Calls run with one worker and no automatic retry. The ignored
SQLite ledger saves a reservation before dispatch and holds full exposure for
unknown delivery. A returned response with invalid evidence retains any
available usage and charge. Changed source, prompt, schema, or output limit
cannot reuse the ledger.

The **total approved cap is USD 1**, shared across both routes. SQLite takes
a write lock before checking settled charges and outstanding reservations,
so concurrent launches cannot each spend the same remaining budget. No new
call is admitted if its reservation would reach the cap. The reservation
uses each pinned endpoint's full published context and maximum completion
limits at its current token rates. It does not rely on the requested
`max_tokens: 320` as a billing ceiling: [OpenRouter says](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)
reasoning tokens are billed output and usually count against `max_tokens`,
but documents occasional provider overrun. The published bounds are 131,072
context plus 117,964 completion tokens for DeepInfra, and 131,072 plus
65,536 for Groq. Their maximum reservations are **$0.024903544** and
**$0.0294912 per call**, respectively. The runner checks these endpoint
bounds before any paid call and fails closed if they are missing or increase.
It runs serially, replacing a reservation with observed usage only after a
settled response. Uncertain calls retain the full reservation. These are
conservative exposure bounds, **not expected charges**. Across 100 calls per
route, a hypothetical sum of all maximum reservations would be about $5.44;
they are never in flight together. A hard guarantee still depends on the
provider honoring its published limits and rates; an account-side key spend
control would provide an independent backstop. The 100 rows have 100
distinct exact texts. No cache reuse is expected within this experiment.

For an independent account-side limit, the user would need to assign the
OpenRouter key a [per-key guardrail budget](https://openrouter.ai/docs/guides/best-practices/spend-controls)
below the remaining USD 1 authorization and verify its existing spend and
reset interval. This changes provider settings, so the runner does not create
or alter it. The local cap is built from the published endpoint token limits
and prices; any missing, increased, or incompatible bound stops paid work.

The original local dry run validated source and baseline hashes, then stopped
at the absent-key gate. The October 7 ledger results supersede that earlier
zero-call state. Offline synthetic tests do not establish live route quality,
privacy acceptance, provider-side budget enforcement, or throughput.

## User-run handoff and next gate

**Hold this command until the uncertain POST is reconciled.** After that,
from this branch's repository root Hanif can run:

```sh
zsh tools/run_openrouter_benchmark_user.zsh 3
```

The script prompts for the existing OpenRouter key with hidden input. It
sets it only for the child process and does not save it. It does not buy
credits or change credential settings. The 3-row smoke covers both routes.
Inspect the ignored ledger and aggregate read-only report before proceeding:

```sh
python3 tools/openrouter_extractor_benchmark.py --source PATH_TO_COST_100 \
  --manifest PATH_TO_MANIFEST --baseline PATH_TO_SAVED_JEV_V2_DB --report
```

If both routes pass privacy, schema, source-evidence, usage, and cap checks,
run `zsh tools/run_openrouter_benchmark_user.zsh 100` to finish the same rows.
The ledger skips successful calls and blocks a new launch while any call is
uncertain or invalid. Reconcile that attempt before a new experiment; this
runner deliberately has no automatic replay of that row. The user should
share only the aggregate report, not a key or raw ledger.

After a live run, report observed failures, semantic spot checks, exact
agreement with Codex (with the non-gold limitation), reasoning-inclusive
usage and cost, request and stage wall times, and cache behavior. Then use
measured per-route rates to project 75,894 distinct nonempty texts in the
first 100,000 rows and 484,189 in the full corpus, with separate no-reuse
comparisons. There is currently no measured hosted throughput or cost for
either route, so no defensible 100,000-row time or spend projection and no
extractor winner yet. The earlier Codex evidence path's roughly 143 serial
hours for the proposed first slice is a separate observed-rate projection,
not a measured hosted result.
