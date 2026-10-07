# What the 500-review checkpoint labeled `other`

**October 7, 2026 — saved Jev v2 development output, not human truth.** Of
500 source reviews, **289 (57.8%)** have primary topic `other`. A read-only
scan found many defensible short, general reactions and a smaller set of
plausible missed specific topics. The examples below are selected judgments,
not a measured error rate. No labels or golden answers were changed or read.

| Saved field for the 289 `other` rows | Count |
| --- | ---: |
| Intent: praise / complaint / cancellation / request / unclear | 184 / 59 / 16 / 4 / 26 |
| Severity: 1 / 2 / 3 / 4 / 5 | 220 / 64 / 4 / 1 / 0 |
| `needs_review=true` | 289 |
| Exact distinct texts / cache reuses | 268 / 21 |
| Text length: ≤3 / 4–10 / ≥11 whitespace words | 152 / 96 / 41 |
| Topic confidence: ≥0.8 / 0.5–<0.8 / <0.5 | 257 / 25 / 7 |

`needs_review` is true for every `other` row by the saved routing rule. The
per-field confidence is a model output, not calibrated accuracy. High topic
confidence can coexist with a plausible miss. Eleven exact text strings
appear more than once; 21 IDs reused a saved result, while all IDs remain
separate records.

## Representative source examples

These short quotes were checked against their saved source rows. IDs are
original source IDs, shown only for the selected examples. No personal
details, golden labels, or full raw files are included.

| Source ID and excerpt | Saved output | Reading under the shared rubric |
| --- | --- | --- |
| `e2fc1a52-c841-4122-8124-02e2ada9a345` — “Best music app” | `other`, praise, severity 1 | General praise with no specific feature; `other` fits. |
| `178c3b49-b689-4fe4-92a2-2257a58e6d95` — “Worst app.” | `other`, complaint, severity 2 | Generic criticism; no specific defect to assign. |
| `a1a28752-3256-4f81-b888-3e943343529f` — “gospel music isn't much” | `other`, complaint, severity 2 | Plausible `catalog` coverage complaint; needs review. |
| `ee17dcd6-07c0-4441-8e64-e7ea57877c78` — “Too much adds” | `other`, complaint, severity 2 | Ad interruptions belong to `usability` if this refers to ad load; likely miss. |
| `e5e362d7-1057-43bf-a3ca-8ffd93f80789` — “The new Lyrics font is so bad.” | `other`, complaint, severity 2 | A specific presentation/control issue, plausibly `usability`. |
| `8cd35162-9223-42d1-8097-06e22fde94ea` — “automatically starts even after you have disabled all permissions” | `other`, complaint, severity 3 | Specific unwanted behavior; test routing to resource use or controls. |
| `45c561b9-cc47-4d80-95d3-f0d20bc84af3` — “The update made the app useless” | `other`, cancellation, severity 4 | Topic may stay `other`, but severity 4 needs a clearly blocked core task that this excerpt does not establish. Review full source context. |
| `d5761299-2544-415d-b2a3-ca4c878e0eb2` — “Boycott sewden brands.” | `other`, cancellation, severity 1 | Topic `other` fits; a bare boycott slogan may need `unclear` intent under the stated precedence rule. |

The exact-text content was scanned qualitatively. For orientation only,
case-insensitive literal keyword flags found **12** `other` reviews mentioning
an update, **6** with boycott/Sweden-like terms, **3** with ad terms, and
**1** with “lyrics.” These flags overlap and are neither exhaustive semantic
groups nor ground truth. General praise such as “Best music app” supplies no
specific topic even though it mentions music. Conversely, the selected
catalog, ad, and font complaints name a narrower problem.

## Action worth testing

1. Review the **75 `other` complaint/cancellation rows** first, especially
   the five with severity 3–4, then sample high-confidence `other` praise and
   vague criticism. Keep the saved predictions and record adjudications
   separately; do not relabel all `other` rows.
2. Add bounded development examples for catalog shortage, ad frequency,
   lyrics presentation, unwanted auto-start, and bare boycott slogans to a
   *candidate* rubric/prompt test. Compare against the frozen v2 output before
   changing production configuration; invalidate affected cache use if the
   prompt, model, effort, or schema changes.
3. Use a blind verifier and human-reviewed development sample to measure
   whether changes improve topic and intent decisions. Keep golden answers
   isolated until the final evaluation gate. `other` prevalence alone is not
   evidence that the classifier is inaccurate.

Source: ignored, read-only `jev_checkpoint500_v2.db` saved classifications
and source text. The [500 checkpoint report](checkpoint-500-readiness.md)
establishes manifest identity, all-ID completion, and exact evidence spans;
those mechanical checks do not establish semantic label quality.
