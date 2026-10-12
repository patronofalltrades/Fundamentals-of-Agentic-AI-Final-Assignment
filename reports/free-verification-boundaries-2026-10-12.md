# Free verification boundary check — 12 October 2026

This check used local code and saved data. It made no model or paid call. Its
synthetic cases exercise identity, exact-span, and public-output checks; they
do **not** measure whether a model resists an injected instruction or detects
a planted label error.

## Saved verifier material

The issue-map report saves only aggregate model-verifier agreement: 511/600
(85.2%). Its file hash list covers agent labels, membership, and rankings, but
does not name a per-case verifier prediction artifact. No 600-case verifier
prediction file was found in the inspected local handoff. A corrupted-label
replay cannot be honestly reported from this aggregate.

A separate frozen 40-case model-prediction file has 40 distinct original IDs.
Local code checked that all 40 IDs and source hashes match its saved blind
manifest and that its declared manifest SHA-256 matches the file. It records a
catalog hash, model, and prompt version. It does not record a configuration
hash or per-case blind-input digest, much less proof that the first prediction
was hidden. It is not the
reported 600-case verifier output and is not evidence that a model caught a
planted corruption.

To test planted-error detection with a real saved verifier, preserve the
per-case verifier predictions and a frozen blind-input manifest. Match original
IDs, source hashes, catalog/configuration, prompt version, and creation order
before any corruption. Record which primary labels were deliberately changed,
without putting those labels into the verifier input. Then score verifier
disagreements against the planted set. Agreement with a different model would
still be model-to-model evidence, not human accuracy.

## Synthetic checks

`tests/test_free_verification_evidence.py` passed four tests. A deliberately
changed synthetic issue label yielded one disagreement; altered IDs, source
hashes, or configuration were refused. Synthetic instruction text was treated
as source data by the exact evidence validator: a source-exact quote passed and
fabricated quote/entity spans failed. A private manifest inspection returned
metadata only. The public boundary capped a synthetic
excerpt, detected an example email, and converted an exception-like reason to
a fixed category. No model was invoked, so this is an application boundary
test only.

## Private text-free trace

`tools/free_verification_evidence.py` wrote one deterministic accepted case
and one quarantined case to an ignored, mode-0600 local JSON file. It selected
the lexicographically first eligible source ID in `USE-ADS`, linked its saved
source row hash and configuration to membership, recomputed the issue's 5,197
baseline members and 11,874 severity sum, matched two saved claims, and
checked those exact claim lines in the saved memo. The failed case records an
original ID and source hash, state, and sanitized reason category; it omits
the raw exception and all review text. The private trace SHA-256 is
`b7385da77d43a707955811c73444a400a211905552d734de348c6e1e84bb4408`.
The trace is local evidence for a human reviewer, not a public artifact or a
review of semantic correctness.

## Fresh human sample gate

No new human sample was created. A reproducible plan is to freeze the current
predictions, rank candidates by SHA-256 of a versioned seed and original ID,
take a small fixed count per saved topic, and exclude matching original IDs
**and exact-text hashes** from all prior review sets before writing a blank
mode-0600 sheet. The 64-case design, 100-case pilot, and 40-case blind grouping
manifests are locatable. An approved exclusion manifest for the golden set and
any other previously reviewed cases was not available without reading their
contents. Obtain that IDs/text-hashes-only manifest first; do not open golden
answers or call the sample untouched until every exclusion is verified.

The human blind agreement remains 16/40 (40%) before overrides. Numeric claim
checks and this trace do not establish semantic accuracy or a causal or revenue
effect. Nothing was pushed, merged, deployed, or uploaded.

## Reproduction

- `python3 -m unittest tests.test_free_verification_evidence -v`: four synthetic tests passed.
- `python3 -m unittest discover -s tests -t . -q`: 257 tests passed with localhost socket permission for the existing HTTP test.
- `python3 -m tools.free_verification_evidence --db <private accepted dashboard DB> --memo dashboard/provisional_memo.md --out local/<new trace>.json`: emitted the aggregate trace result above. Run only with a new ignored output path; do not publish the output file.
- `inspect_prediction_manifest(<saved 40-case predictions>, <frozen blind manifest>)` returned 40 matched IDs/hashes, a matching declared manifest digest, and no configuration hash or per-case blind-input digest. This function emits metadata only.
