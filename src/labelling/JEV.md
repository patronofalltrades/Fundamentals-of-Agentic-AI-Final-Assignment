# JEV (BeatAPI Decisions API): enrichment provider prep

Prepared Oct 5, 2026 from https://docs.beatapi.io/decisions (incl. `#free-calls`), `/quick-guide`,
`/development`, `/text-api`. Pairs with `PREP.md` (the record/calls contract) and `jev_client.py`.
Nothing here has been run against the live API yet; every number marked *est.* must be replaced
by measured `cost_100` pilot data.

> **Update Oct 5, 2026: provider is now TypeSafe direct.** Hanif has a TypeSafe account. The
> canonical client is `model_client.py` (OpenCode), whose `create_client()` now defaults to
> `provider="typesafe"` → `https://api.typesafe.ai/v1/systemone`, model `jev-latest`, key from
> `TYPESAFE_API_KEY` (in `.env`, git-ignored). The request format is the same as BeatAPI's, so the
> schema mapping below still applies. BeatAPI's rate-limit and cost figures (§2) no longer apply;
> re-measure in the `cost_100` pilot. `jev_client.py` is superseded and kept only for reference.

## 1. What JEV is (and isn't)

| | |
|---|---|
| Endpoint | `POST https://api.beatapi.io/v1/systemone` (alias `/v1/decisions`) |
| Auth | `Authorization: Bearer $BEATAPI_API_KEY` (key from beatapi.io → Dashboard → API Keys) |
| Models | `jev-1.13-free`: $0 in/out, works on zero balance. `jev-1.13`: $0.042 / 1M input tokens, output not billed |
| Input | `state` (string or JSON object) + named `questions` |
| Question types | `noul` → probability 0–1 · `choice` → winning option + probability distribution + confidence · `score` → position on a 0-indexed scale + distribution + confidence |
| Limits | 32,000 tokens for state + questions combined; no streaming; no sampling params |
| Usage | Response carries `id`, `model`, `answers`, `usage.input_tokens/output_tokens`, which map directly to `calls.jsonl` |

**JEV does not generate text.** It cannot write an `evidence_quote` or list `entities`. It also
can't name issue groups or write the memo. So it covers the **enrich** role, and probably
**verify**, but not **group** or **memo** (see §6).

## 2. Rate limits (decides the plan)

From `#free-calls`: *"one successful request per minute before your first top-up, at most ten per
minute after any top-up however much was paid."* Over the limit you get `429 rate_limit_exceeded` + `Retry-After`.
Free calls are counted separately from paid limits. Paid calls use the key's allowance (up to
120 req/min per key; tier grows with lifetime top-ups) plus an account concurrency limit
(`GET /v1/usage` → `concurrency.limit`).

Full run = **484,189 distinct texts** (exact-text cache covers the other 176,420 repeats).

| Setup | Reviews/request | Requests | Wall time at the limit | API cost *est.* |
|---|---:|---:|---|---|
| Free, no top-up (1/min) | 25 | 19,368 | **~13.4 days**. Misses the Oct 13 deadline | $0 |
| Free, after any top-up (10/min) | 25 | 19,368 | ~32 h (+ retries, verify) | $0 |
| Free, after any top-up (10/min) | 50 | 9,684 | ~16 h | $0 |
| Paid `jev-1.13` (≤120/min) | 25 | 19,368 | ~3 h at the cap | ~$10 base (≈480 tok/review × 484k × $0.042/M); ~$15 conservative |

**Recommendation:** top up a small amount (e.g. $5–10). That unlocks 10/min on the free model and
makes paid JEV available as a fallback. Pick **one** model for the whole run and keep it fixed:
`label_config` includes the model, so switching models invalidates the cache and creates mixed
configs. The free model at 10/min is feasible but leaves little slack before Oct 13. Paid
`jev-1.13` costs about $10 and finishes in hours, which leaves time for checkpoint, verify and
resume demos. The free model's 1/min limit is fine for `cost_100` and `checkpoint_500` only if you
haven't topped up yet (100 reviews / 25 = 4 requests).

## 3. Mapping the A5 schema onto JEV

One request packs N reviews (contract max 50). `state = {"rubric": {...full definitions once...},
"reviews": {"r01": text, ...}}`. Each review gets namespaced questions (`r01__topic`, …).

| Record field | Source | Rule (in `jev_client.py`) |
|---|---|---|
| `topic` | JEV `choice` over 8 topics | validated ∈ contract set |
| `intent` | JEV `choice` over 5 intents | precedence cancellation > complaint > request > praise > unclear stated in rubric |
| `severity` | JEV `score` over 5 levels | `round(score) + 1`, clamped, exact `int` 1–5 |
| `sentiment` | JEV `score` over 5 valence levels | `(score − 2) / 2` → [−1, 1] |
| `needs_review` | JEV `noul` + confidence | true if noul ≥ 0.5 **or** topic/intent confidence < 0.5 (thresholds tuned on dev samples only, **never golden**) |
| `evidence_quote` | JEV `choice` over the review's own sentences; single-sentence reviews → whole stripped text | always an exact substring by construction; re-checked before returning |
| `entities` | code: fixed feature lexicon | only emitted when the term literally appears in the text (`[]` allowed) |

`label_config` = `beatapi/<model>:prompt-jev-v1:schema-a5-v1:pack<N>`. Pack size is included
because packing changes what the model sees.

Measured payload size (dry-run, chars/4): 1 review ≈ 1,090 tok · 10 ≈ 517/review · 25 ≈ 478/review ·
50 ≈ 465/review (~23k, close to the 32k cap for long reviews). **Start at pack 25.** The client
refuses oversize payloads so the harness can split the batch.

## 4. Open risks to test in `cost_100` / `checkpoint_500`

1. **Packing quality.** Does JEV keep 25 reviews separate, or do labels bleed between `r01`/`r02`?
   Run `checkpoint_500` at pack 1 vs pack 25 on the same rows and compare agreement. Use pack 1 if it bleeds.
2. **Max questions per request is undocumented.** Pack 25 gives ~125–150 questions. If the API
   rejects that (400), drop to pack 10.
3. **Score semantics.** Docs show `score` as a continuous 0-indexed value, so rounding to the nearest
   level is our mapping, not JEV's. Inspect the score distribution in the pilot.
4. **Token counts.** The ~480/review figure is a character estimate; read the real `usage` from the pilot.
5. **Free-tier counting.** Only *successful* requests count toward 1/min; 429s still cost wall time.

## 5. Error → harness mapping

| HTTP / code | Class in client | Harness action |
|---|---|---|
| 429 `rate_limit_exceeded`, 500, 503 | `TransientModelError` | client honours `Retry-After`, backoff + jitter, ≤4 retries; log each attempt `outcome:"failed"` |
| 400, 401, 402 `insufficient_credits`, 403, 404 | `ModelClientError` | do **not** retry; stop the run (402 = top up) |
| Missing answer, bad choice, non-substring quote | `InvalidModelOutput` | one retry, then quarantine the batch's IDs with a reason |

Every request sends an `Idempotency-Key`, so a retried submit can't be charged twice.

## 6. Other roles

- **verify**: JEV *can* re-label with differently worded instructions, but using the same model
  weakens the independence claim. Better: a different model on the same key via BeatAPI's Text API
  (`/v1/chat/completions`, list models with `GET /v1/models`). That decision belongs to ChatGPT (evals).
- **group / memo**: needs text generation → Text API model, not JEV.

## 7. Try it

```bash
# offline: builds the real payload, fake answers, no key needed
python3 src/labelling/jev_client.py --show-payload

# one real call, 2 demo reviews, free model (after putting your key in .env / shell)
export BEATAPI_API_KEY=...        # never commit
python3 src/labelling/jev_client.py --live
```

Once infra delivers `model_client.py`, `jev_client.py` imports the shared types from it
automatically. `create_client(config)` returns the dry-run client unless `BEATAPI_API_KEY` is set
and `dry_run` is false.
