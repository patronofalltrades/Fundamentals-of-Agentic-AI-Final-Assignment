# Issue grouping v3: offline gate status

The frozen pilot rule is `pilot-primary-problem-v3-20261010`. The two private
decision sheets still match their verified SHA-256 digests
`a6201fd8ca1f394105b06977635a77b1f40bb80eadb1087bbfbc6543d130b3ae`
and `897ebc95fc2913cd704de3a3168c854ecd735d22f3ce46a3cd0ed28f893f540f`.
The 40-case independent review sheet was completed after this original gate
note. Its source identity and aggregate comparison are recorded in
[the independent check](issue-grouping-independent40-score.md). That check is
agreement with one assistant's assignments, not production grouping accuracy.

Six recorded `correct_saved_label` decisions identify cases 18, 43, 61, 80,
89, and 94. The verified sheets have no structured replacement-label or
replacement-quote fields. Free-form notes are not applied as corrections. A private
six-row correction sheet now preserves each saved source, label, and quote
beside blank replacement fields. Its SHA-256 is
`fc7f4ce0c0fbc00917bcf90226bb704bab13c420943011d499b2255abef8707d`.
The validated intake snapshot has SHA-256
`e04e76ad6d0e453688919be42bf50571ba8e1d4cc043df8bd66c0a57a2ee5623`:
six pending, zero validated corrections, zero production memberships. The
validator requires an explicit human confirmation and rationale, changed
valid label fields or a changed exact-source quote, and unchanged source
identity. It records a separate private overlay; it never rewrites saved
model output or applies membership.

## Smallest remaining human work

1. Enter or leave unresolved the five blank pilot issue decisions: 22, 29,
   31, 81, and 97. A general instruction to continue is not a decision for
   these cases.
2. Review the six correction cases and enter exact replacement fields with
   rationale where a saved label or quote is wrong. The prepared sheet has
   no replacement values prefilled.
3. Review the 40-case aggregate agreement and privately adjudicate the
   disagreements before deciding whether the v3 mapping rule is usable.

The v3 catalog is still `pilot_authorized`, with
`production_approved=false`. No full 30,403-record issue mapping, ranking,
memo, or recommendation has been produced. The ranker continues to reject
the pilot catalog.

## Dashboard handoff

The accepted-evidence export has 100,229 accepted original IDs, but a saved
issue map and ranking are still absent. The dashboard import contract records
public API blockers: source-position detail routes, full evidence quotes,
individual nonaccepted reasons, and missing known-semantic-flag exclusions
from issue queries. The reported Vercel preview check does not verify those
privacy and ranking gates. Resolve and test them in the dashboard owner's
worktree before public import or deployment. No dashboard file was changed
here.
