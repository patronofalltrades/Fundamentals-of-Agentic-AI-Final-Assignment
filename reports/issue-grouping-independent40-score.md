# Independent 40-case grouping check — October 12, 2026

**Attribution clarified on 15 October:** the predictions in this report are
one assistant's manual issue assignments. The 16/40 (40%) exact agreement is
with the human answers; it is not an evaluation of the production grouping
model. Scores and frozen files are unchanged. See the
[attribution audit](evaluation-attribution-and-inclusion-2026-10-15.md) for
the separate claims in older production-agent audit reports.

The completed human sheet has 40 source-matched, nonempty issue decisions and
40 rationales. All issue IDs occur in the frozen 41-issue v3 catalog. Five
answers include uncertainty notes. The sheet changed from its original blank
hash, as expected. The frozen manifest and catalog still match their recorded
SHA-256 hashes.

The assistant assigned one issue to each of the 40 manifest cases from the source text and
v3 definitions, then saved and hashed the prediction file before running the
aggregate-only scorer. The scorer did not print individual answers, case
differences, source IDs, or review text.

| Measure | Result |
| --- | ---: |
| Exact issue agreement | 16 / 40 (40%) |
| Issue-family agreement | 21 / 40 (52.5%) |
| Human answers with uncertainty notes | 5 / 40 |
| Valid, source-matched human decisions | 40 / 40 |

The human CSV SHA-256 is
`8a095149bcca93912732a2b71493d1dbc460d098f03bf8ccd9571737838eb4b1`.
The local prediction CSV SHA-256 is
`68e6782c47795394b69f1ea351cd6db6d28300e8cbba4d0d82e0d19a8c5ba7b5`.
The frozen manifest SHA-256 is
`65c3d9ad0342099860a1977765fa88c419c17c584464513b0cd8e22d44df0f28`.

This is agreement between one assistant's manual assignments and the human
sheet. No production grouping model produced these predictions. Before the
predictions were frozen, aggregate-only validation exposed the human issue
family counts, but no case-level answers. This limits the independence of the
comparison. The sample is five cases per saved broad topic, not a prevalence
sample of the 30,403 grouping candidates. The result does not establish
production mapping accuracy or justify production approval.

The five unresolved pilot decisions and six pending saved-label corrections
remain separate gates. Review disagreement patterns and rule boundaries
privately before a revised pilot or production decision.
