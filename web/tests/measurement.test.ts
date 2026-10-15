import { test } from "node:test"
import assert from "node:assert/strict"
import { verificationState } from "../src/lib/measurement.ts"
import { fmt } from "../src/lib/api.ts"

test("sample verification stays a sample, even when every selected output exists", () => {
  for (const observed of [980, 1000]) {
    assert.equal(verificationState({ blind_verifier: "sample_measured", verification: {
      status: "sample_measured", observed, selected: 1000, missing: 1000 - observed, not_human_accuracy: true,
    }}), "sample")
  }
})

test("absent or inconsistent verification evidence stays pending", () => {
  assert.equal(verificationState({ blind_verifier: "saved" }), "pending")
  assert.equal(verificationState({ blind_verifier: "pending" }), "pending")
  assert.equal(verificationState({ blind_verifier: "sample_measured", verification: {
    status: "sample_measured", observed: 980, selected: 1000, missing: 0, not_human_accuracy: true,
  }}), "pending")
})

test("small measured replay times remain visible; absent time is not zero", () => {
  assert.equal(fmt.value(0.03083695799999997, "seconds"), "30.84 ms")
  assert.equal(fmt.value(null, "seconds"), "—")
  assert.equal(fmt.value(0, "seconds"), "0.0 s")
})
