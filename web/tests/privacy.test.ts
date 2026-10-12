import { test } from "node:test"
import assert from "node:assert/strict"
import { existsSync, readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"

const root = fileURLToPath(new URL("../src/", import.meta.url))

test("public page excludes the full-text development walkthrough", () => {
  const page = readFileSync(`${root}pages/index.astro`, "utf8")
  assert.doesNotMatch(page, /ReviewWalkthrough|id="example"/)
  assert.equal(existsSync(`${root}lib/walkthrough.ts`), false)
})
