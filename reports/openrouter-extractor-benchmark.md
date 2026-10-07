# Hosted evidence extractor benchmark: row-level skip ready

**Latest continuation state:** The user-started process has stopped. DeepInfra
finished its 100 source rows with **91 accepted and 9 failed**. Groq has
**66 accepted, 16 failed, and 18 untouched**. The last Groq response was a
metered provider JSON-validation error with no usable content: 397 output
tokens, all reported as reasoning, exceeded the requested 320 limit. It
remains failed with its full reservation held. A narrow offline repair skips
only this exact pinned, metered provider error when the output remains within
the published endpoint bound; it does not accept evidence, retry, or weaken
source-span checks. The read-only plan now shows 18 new Groq calls, 66 Groq
reuses, 16 Groq failed rows, and no further DeepInfra calls. No paid request
has run after this repair.

Known usage-derived charges are **$0.006082951** across both routes; shared
cap exposure is **$0.725867396** including all held reservations, leaving
$0.274132604 before the strict $1 cap. DeepInfra's 101 historical attempts
(including the old uncertain POST) used 219.583 summed request seconds; its
91 accepted requests used 188.593 seconds. Groq's 82 attempts used 63.925
summed request seconds; its 66 accepted requests used 50.136 seconds. These
are request durations, not measured end-to-end wall time. At Groq's observed
average, the 18 untouched rows would add about 14 seconds of request time
and about $0.00086 of known charges, with substantial uncertainty from
failures and held reservations. The local cap remains binding.

**Partial comparison:** 63 source reviews have accepted evidence from both
routes. Both routes chose the same exact quote on 52/63 and the same entity
list on 43/63. Against saved Codex development evidence on these same rows,
both matched the quote on 42/63; DeepInfra matched entities on 49/63 and
Groq on 39/63. This is agreement with a development baseline, not human
truth. In six reviewed complaint cases, both routes selected relevant exact
source evidence; DeepInfra more often chose a focused excerpt while Groq
sometimes returned the whole review. Each also missed an entity the other
and Codex identified in a different case. The paired set is skewed toward
`other` topics (45/63) and praise (34/63), so it is not a balanced quality
sample. **Provisional extractor choice: DeepInfra**, because it completed
91% of the source set versus Groq's 66% so far, with lower known charge and
better paired entity agreement. Groq is faster, but its 11 provider JSON or
schema errors among 82 attempted rows make completion less reliable. Revisit
after the last 18 Groq rows and a harder paired sample.

**Earlier continuation state:** DeepInfra had 36 accepted, 3 failed, and 61
untouched source rows. Groq had 27 accepted, 2 failed, and 71 untouched.
The second Groq failure was a metered upstream strict-schema rejection:
`/entities` was an object instead of an array, `finish_reason` was `error`,
and the response had no usable content. The specific Groq schema rejection
is now quarantined without retry or accepted evidence. Known ledger charges
are **$0.002139617**; shared cap exposure, including all held reservations,
is **$0.160537312**. No route has five consecutive row-output failures.
The read-only plan admits 61 new DeepInfra and 71 new Groq requests within
the same approved 100-review scope. No paid request has run after this
streak-policy change.

**October 7 incident, after the smoke:** Hanif launched the approved
100-development-review continuation. It saved no further accepted evidence.
DeepInfra attempt 8 returned a response, then local evidence validation raised
`ValidationError`. The runner stopped without an automatic retry. An
authenticated OpenRouter generation log confirms generation
`gen-1791346049-zjFNXPVSGXeCPpv4ydkv` on pinned DeepInfra
`openai/gpt-oss-120b`, HTTP 200, finish reason `stop`, one upstream attempt,
no fallback, 186 input tokens, 185 output tokens including 118 reasoning
tokens, and a displayed rounded charge of $0.0000383. The local ledger's
usage-derived charge is **$0.000038332** and its measured request duration is
4.365 seconds. OpenRouter displayed 3.9 seconds of generation time. These
durations describe this request, not the whole benchmark stage.

The exact validation failure is **unknown**. The prior ledger saved only the
exception class and usage, and OpenRouter reports that I/O logging was not
enabled for this generation. The response content cannot be reconstructed
from the available records. A bounded offline repair now saves the validator
detail and received response in the ignored local ledger on any *future*
invalid response. It does not change evidence validity, privacy routing,
budget accounting, or retry policy. A synthetic regression verifies retained
usage, the response, the diagnostic, the full reservation, and zero automatic
retries. It cannot diagnose the already completed attempt 8.

The six successful calls still cover only three distinct source reviews on
each route: **3 DeepInfra and 3 Groq successes**, plus DeepInfra attempt 8
invalid and attempt 2 reconciled as no visible bill. Known usage-derived
charges across the ledger total **$0.000205352**. The two held DeepInfra
reservations total **$0.049807088**, giving **$0.049974108** aggregate cap
exposure under the $1 authorization. The read-only 100-row plan now shows
DeepInfra 3 reuses, 96 untouched rows, and 1 validation-failed row; Groq has
3 reuses and 97 untouched rows. The validation-failed row is skipped without
retry and never counted as accepted evidence. Neither its observed small
charge nor its normal finish reason justifies releasing the reserved exposure
or accepting unvalidated evidence.
No larger inference run or human golden evaluation occurred. The semantic
comparison and scale recommendation remain pending.

**Baseline:** The 3-row smoke saved three successful results per pinned
route. The validated development overlay has been applied to a separate,
ignored 100-row baseline. Its SHA-256 is
`340153ef37c1bd49f28392e88ca10685343a68480bf32f7186583d85b656960b`.
The source overlay SHA-256 is
`feeba27e2ed1a1b54c625ea6ccfde7048c93312b4ffb237130489e5988071cf0`.
Exactly one of four explicit human topic corrections intersects the supplied
`cost_100.csv`; 285 other checkpoint review rows are unreviewed. The
original Jev database and overlay remain unchanged. This is a development
comparison baseline, not a revised rubric or human golden evaluation. The
100-review continuation later resumed; see the latest state above.

**Row-level failure policy:** A received response may be skipped only when
it failed evidence JSON or exact-source validation *after* pinned provider,
normal finish, token bound, response ID, request fingerprint, and metered
usage checks. The failed attempt, response when available, diagnostic, and
full reservation stay in the ignored ledger. It is never retried
automatically. Five consecutive confirmed row-output failures on one route
pause that route, durably across process restarts; an accepted result breaks
the streak. Historical isolated failures do not accumulate into a stop.
The other approved route may continue. Any uncertain delivery, missing usage,
route mismatch, truncation,
budget failure, or privacy/catalog failure still stops immediately. This is
an offline code change; no new paid request has tested the continuation.
Reports state the 100-source denominator, per-route accepted and failed
counts, and the count of source reviews accepted by both routes. Compare
models only on that paired subset, while disclosing coverage loss.

| Route | Successful calls | Known charge | Input / output tokens | Reasoning tokens | Summed request time |
| --- | ---: | ---: | ---: | ---: | ---: |
| DeepInfra 120B | 3 | $0.000044545 | 455 / 163 | 76 | 10.059 s |
| Groq 20B | 3 | $0.000122475 | 689 / 236 | 157 | 2.245 s |

The six known charges total **$0.000167020**. Shared cap exposure is
**$0.025070564**, including attempt 2's full **$0.024903544** hold. The
smoke added no failed requests. Read-only replay validated all six saved
source hashes, exact quotes, whole-boundary entities, and response provider
names. All six quotes and entity lists exactly matched saved Codex evidence.
The three source rows are short praise with no named entities; all three
models chose the full review as the quote and an empty entity list. This is
a weak semantic test of complaint extraction and is not human accuracy.
DeepInfra averaged 3.353 seconds per saved request and Groq 0.748 seconds;
these are summed request durations, not measured stage wall time. The runner
verified both endpoint listings before the successful smoke and sent the
pinned provider, strict schema, no fallback, data-collection deny, and ZDR
settings. The saved provider names matched the pins. This establishes live
request acceptance, not an independent audit of provider privacy behavior.

**Input identity repair:** The original ledger did not record the full
supplied labels or exact request payload per successful call. The revised
runner fingerprints source-row hash, complete label JSON, the label
configuration hash, prompt version, and the full provider/model/schema/
effort/output-limit payload before dispatch. A changed fingerprint cannot
silently reuse a saved result. Repeat calls require a separate explicit flag
and are counted in a read-only plan before spending. The six historical
successes were bound to the still-frozen Jev baseline with provenance
`inferred_from_frozen_baseline`; their original request payloads were not
saved, so this binding is an inference. All attempts and charges remain.
With the corrected baseline, the read-only 100-review plan is **3 reuses
and 97 new calls per route**, with **zero changed-input repeats**. The one
corrected row had no saved hosted extractor result. No larger run has started.

**October 7 account reconciliation check (10:18 UTC):** The authenticated
OpenRouter Personal account showed only one billed generation on the
"Berkeley Haas AI Class" benchmark key over the past month: the saved
DeepInfra generation `gen-1791335333-SQKkJa6OK6BXhV9Bdb10`, with 156 input
and 49 output tokens and a displayed rounded charge of $0.0000141. The
account activity summary for that key showed 205 tokens, exactly that one
request's total. The account's 24-hour upstream request table showed only
the same DeepInfra request, status 200. There was no matching billed second
generation visible about nine hours after the reported connection loss.
The UI displayed times in GMT+7; its 08:08 Oct 7 first call is 01:08 UTC.
The uncertain attempt lacks a saved provider ID and exact dispatch time,
so this is evidence of no **visible settled bill**, not proof that its POST
never arrived. Ledger attempt 2 now has an explicit account-check record and
status `reconciled_no_visible_bill`. Its full $0.024903544 reservation remains
held. A retry requires an explicit attempt ID and is saved as a new attempt.
No new inference was sent during this check.

**Decision:** Do not start the 100,000-row inference run. The approved
100-review scope remains incomplete. Row-level validation skip is ready for
a controlled continuation through the existing hidden-key launcher. The
two-route quality comparison is incomplete.

**October 6 live preflight update:** Hanif's smoke command stopped on the
public catalog check before sending a review. The pinned DeepInfra 120B
entry then had `status: -5`; the requested Groq 20B entry had
`status: 0`. The endpoint tags and model IDs still match. The validator's
`status != 0` hold is operating as written; there is no demonstrated parser
bug and no basis to substitute another provider. A read-only ledger check
found **zero call rows, zero reservations, and zero charges at that time**.
A regression fixture checks this fail-closed status case.

**October 7 connection-loss history, before the successful smoke:** The ignored ledger contained one
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
in-flight inference. The account check above found no visible second bill;
the saved attempt and full reservation remain in the ledger. The later
smoke demonstrated request acceptance on both pinned routes for three rows.

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
The account check found no visible settled bill for attempt 2; no response
was saved, so its delivery outcome remains unknown. The full reservation
stays held. Only an explicit retry can resume that row.

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
policy is silently relaxed. The successful smoke verified access to both
pinned routes under those request settings.
The public endpoint listings do not expose a per-endpoint ZDR field. They
therefore do **not** establish ZDR independently. Both live routes accepted
requests carrying `zdr: true`; if a later request fails, stop instead of
removing the safeguard.

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
cannot reuse the ledger. The revised request fingerprint also blocks reuse
when full labels, their configuration, model, provider, or effort changes.

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
at the absent-key gate. The October 7 smoke supersedes that earlier zero-call
state. Synthetic tests alone do not establish live quality or provider-side
budget enforcement.

## User-run handoff and next gate

The 3-row smoke is complete. The validated overlay is incorporated in an
ignored corrected baseline, and the read-only plan confirms three reuses
and 96 new DeepInfra calls, 97 new Groq calls, one skipped DeepInfra row,
and no changed-input repeats. Inspect the
ignored ledger and aggregate report without a key:

```sh
python3 tools/openrouter_extractor_benchmark.py --source PATH_TO_COST_100 \
  --manifest PATH_TO_MANIFEST --baseline PATH_TO_REVIEWED_BASELINE_DB \
  --plan --limit 100
python3 tools/openrouter_extractor_benchmark.py --source PATH_TO_COST_100 \
  --manifest PATH_TO_MANIFEST --baseline PATH_TO_SAVED_JEV_V2_DB --report
```

The approved 100-review launch uses
`zsh tools/run_openrouter_benchmark_user.zsh 100` from this checkout. The
launcher checks the corrected baseline SHA-256 before requesting the key.
The user enters the existing key at its hidden prompt; no key is saved or
requested in chat. The ledger keeps the earlier reconciled attempt's full
reservation in total exposure. If a route or privacy check fails, stop.

After a live run, report observed failures, semantic spot checks, exact
agreement with Codex (with the non-gold limitation), reasoning-inclusive
usage and cost, request and stage wall times, and cache behavior. Then use
measured per-route rates to project 75,894 distinct nonempty texts in the
first 100,000 rows and 484,189 in the full corpus, with separate no-reuse
comparisons. The three trivial smoke rows give limited hosted speed and cost
data, but no defensible 100,000-row projection or extractor winner yet.
The earlier Codex evidence path's roughly 143 serial
hours for the proposed first slice is a separate observed-rate projection,
not a measured hosted result.
