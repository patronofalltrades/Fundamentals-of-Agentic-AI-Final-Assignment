# Jev entity boundary bug

Hanif authorized recording and fixing the entity validation bug. This repair lives on `fix/jev-entity-boundaries` in its own worktree. It is not integrated or published.

## Observation

The prior validator accepted an entity when it appeared anywhere inside the source text. A synthetic `ad` or `ad ` entity therefore passed against `bad experience`. The alignment helper could also copy `ad` from inside `bad`. Exact substring checks alone did not establish a whole-word entity.

The ignored 100-review pilot ledger has 100 saved evidence records and 93 entity mentions. An offline read-only check found no saved `ad` or `ad ` entity. All 100 records pass the repaired entity and quote validator. This is a structural check; it does not measure semantic accuracy or human agreement. Saved outputs were not changed.

## Repair

- Reject entity strings with leading or trailing whitespace.
- Require at least one exact source occurrence with word boundaries on both edges. Unicode letters, numbers, combining marks, and underscores count as word characters. Internal spaces and punctuation remain unchanged, so names such as `C++` and non-Latin text can still be exact entities.
- Apply the same boundary check when aligning an entity across case or internal whitespace differences. Keep quote alignment and exact-substring validation separate from entity rules.
- Add synthetic regression tests for partial `ad` in `bad` and `ads`, a real `ad`, edge whitespace, case and newline alignment, punctuation, and Unicode text.

The repair copies the original Jev worktree's two uncommitted files before editing them. No model calls, paid requests, golden answers, or output rewrites are part of this fix. The coordinating owner should review the diff and integrate it with the active Jev branch after that branch's other work is ready.

## Checks and limits

- `python3 -m unittest discover -s tests -t . -v`: 158 synthetic/offline tests passed.
- `python3 -m spotify_pipeline --help`: exited successfully.
- Read-only replay of the ignored pilot ledger: 100 of 100 evidence records and all 93 entity mentions pass the repaired validator.
- Word edges are conservative for scripts without spaces. A legitimate shorter entity embedded in a continuous run of Unicode letters may need a longer exact source span or human review.

These checks do not establish model quality or human agreement. The active Jev branch's mixed saved evidence versions (90 `evidence-extract-v1`, 10 `evidence-extract-v2`) were not regenerated. Its original worktree remains the integration owner.

## Integration review

The repair branch starts from Jev commit `e773e949` and includes byte-for-byte copies of the original worktree's two preexisting uncommitted v2 files before the boundary edits. A file comparison with that worktree shows only the boundary repair and its new tests in those files. The original worktree and its ignored databases are unchanged.

Do not cherry-pick this combined branch directly into the dirty Jev worktree. The coordinating owner should first record or hand off the original v2 changes, then review this branch's diff and integrate it in a clean worktree. Run the affected suite after integration. No branch has been pushed.
