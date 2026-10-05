# Review request: whole-word entity matching (extract-v2)

Branch `fix/labelling-entity-boundaries`, from `origin/opencode-labelling` 08eb6cc. Prepared by Claude Opus (infra) at Hanif's request; OpenCode owns `src/labelling/` and decides whether to merge.

## The bug
`extract.py` v1 matched lexicon needles as raw substrings. `"ad "` fired inside "bad ", "read ", "had ", so most "bad app" reviews got `entities: ["ads"]`. The same flaw hit `lag` ("flag"), `search` ("research"), `support` ("unsupported"), `charge` ("recharge"), `data` ("database"). The quote picker also searched sentences for the entity *name* (`"ads"` matched "downloads"; `audio_quality` never matched).

In the measured 100-review pilot (claude-infra `cost/pilot_records.jsonl`), 15 records carried `ads` and 8 of them contained no ad word.

## The fix (`src/labelling/extract.py`)
- Needles compile to whole-word regexes with common inflections (-s/-es/-ed/-ing, final-e verbs: updating, shuffling). `advert*` is a prefix needle. `re:` marks a raw regex.
- "adds" (a misspelling of "ads" in about 8,400 full-corpus reviews) counts as `ads` unless used as a verb ("it adds songs", "adds a feature").
- Added `suggestion` (v2's boundaries would otherwise drop "suggestions").
- `extract_evidence_quote` anchors on the entity's patterns, not its name.
- `EXTRACT_VERSION = "extract-v2"`; `pilot_config.json` `label_config` is now `typesafe/jev-latest:prompt-v1:extract-v2:schema-a5-v1`, so v1 cache entries are never reused for v2 output.

## Evidence
- `python3 -m unittest tests.test_labelling_extract` — 12 tests: partial-word false positives, real ads, "adds" misspelling vs verb, inflections and phrases, lexicon order, quote anchors.
- Offline replay on the 100 pilot texts (no model calls; entities are code-derived): 12 of 100 records change; `ads` false positives removed ("Very bad app", "Vary bad experience", "Most fun i have had recently", gibberish), 3 real ad complaints gained ("adds are too much", "your recommendation adds", "premium adds are everywhere"), `lag` removed from a Hinglish review where v1 matched it inside "alag" (Hindi for "different"). Evidence quotes unchanged for all 100.
- Full corpus (660,622 rows): extraction runs in about 52 s; every evidence quote is an exact source substring.

## Not changed
Jev questions, rubric, model client, `jev_client.py`, and any saved outputs. After merge, the infra side will update `configs/pilot_cost_100.json` to the new `label_config` and re-run the cost_100 pilot (about $0.03).

## Known limits
Lexicon matching is still keyword-based: it can tag a feature that is mentioned but not complained about, and it misses paraphrases. Non-Latin scripts only match via the Latin needles.
