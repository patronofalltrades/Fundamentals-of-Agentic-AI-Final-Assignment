// The review rule from the explainer handoff checklist. Run: npm test (Node 22.18+ strips TypeScript types).
import { test } from "node:test"
import assert from "node:assert/strict"
import { reviewAt, FIELDS } from "../src/lib/walkthrough.ts"
test("handoff checklist thresholds", () => {
  assert.equal(reviewAt(0.6).needsReview, true)
  assert.deepEqual(reviewAt(0.6).low.map((f) => f.name), ["Severity"])
  assert.equal(reviewAt(0.27).needsReview, false)
  assert.equal(reviewAt(0.28).needsReview, true)
  assert.deepEqual(reviewAt(0.66).low.map((f) => f.name), ["Intent", "Severity"])
  assert.equal(FIELDS.severity.confidence, 0.27)
})
