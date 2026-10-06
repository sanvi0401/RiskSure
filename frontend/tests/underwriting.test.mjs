import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"
import { runInNewContext } from "node:vm"
import ts from "typescript"

const exports = {}
runInNewContext(ts.transpileModule(readFileSync(new URL("../lib/underwriting.ts", import.meta.url), "utf8"), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText, { exports })
const filter = exports.filterUnderwritingQueue
const applications = [
  { id: 1, name: "Alice", review_status: "completed", assigned_underwriter_id: 7, final_risk: 0.9, created_at: "2026-01-01" },
  { id: 2, name: "Bob", review_status: "pending", assigned_underwriter_id: null, final_risk: 0.2, created_at: "2026-01-03" },
  { id: 3, name: "Carol", review_status: "in_review", assigned_underwriter_id: 7, final_risk: 0.8, created_at: "2026-01-02" },
  { id: 4, name: "Dan", review_status: "manual_review", assigned_underwriter_id: 8, final_risk: null, created_at: "2026-01-04" },
]
const ids = result => Array.from(result, item => item.id)

test("queue views separate completed, assigned, and unassigned cases", () => {
  assert.deepEqual(ids(filter(applications, "open", 7)), [3, 2, 4])
  assert.deepEqual(ids(filter(applications, "mine", 7)), [3])
  assert.deepEqual(ids(filter(applications, "unassigned", 7)), [2])
  assert.deepEqual(ids(filter(applications, "completed", 7)), [1])
})

test("name and case-number search apply within the selected queue view", () => {
  assert.deepEqual(ids(filter(applications, "open", 7, "  CAR ")), [3])
  assert.deepEqual(ids(filter(applications, "open", 7, "#2")), [2])
  assert.deepEqual(ids(filter(applications, "open", 7, "Alice")), [])
})

test("sorting is stable, leaves the input alone, and puts unknown risk last", () => {
  assert.deepEqual(ids(filter(applications, "open", 7, "", "newest")), [4, 2, 3])
  assert.deepEqual(ids(filter(applications, "open", 7, "", "risk")), [3, 2, 4])
  assert.deepEqual(ids(applications), [1, 2, 3, 4])
})
