import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"
import { runInNewContext } from "node:vm"
import ts from "typescript"

const source = readFileSync(new URL("../lib/api.ts", import.meta.url), "utf8")
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText

function harness() {
  const calls = []
  const timers = []
  const cleared = []
  const exports = {}
  runInNewContext(compiled, {
    exports, process: { env: {} }, Headers, AbortController, DOMException,
    fetch: async (url, init) => {
      calls.push({ url, init })
      return new Response('{"verified":true}', { headers: { "Content-Type": "application/json" } })
    },
    setTimeout: (callback, milliseconds) => { timers.push(milliseconds); return timers.length },
    clearTimeout: (id) => cleared.push(id),
  })
  return { api: exports, calls, timers, cleared }
}

test("ordinary API calls retain their 30-second deadline", async () => {
  const { api, timers, calls, cleared } = harness()
  await api.apiFetch("/health")
  assert.deepEqual(timers, [30_000])
  assert.equal(calls[0].url, "/api/health")
  assert.deepEqual(cleared, [1])
})

test("AI JSON calls receive a bounded deadline without forwarding the custom option", async () => {
  const { api, timers, calls } = harness()
  const result = await api.apiJson("/cases/1/assistant", {
    method: "POST", body: '{"question":"Evidence"}', timeoutMs: 90_000,
  })
  assert.equal(result.verified, true)
  assert.deepEqual(timers, [90_000])
  assert.equal("timeoutMs" in calls[0].init, false)
  assert.equal(calls[0].init.method, "POST")
  assert.equal(calls[0].init.headers.get("Content-Type"), "application/json")
  assert.equal(calls[0].init.signal.aborted, false)
})

test("an explicit authorization header remains intact", async () => {
  const { api, calls } = harness()
  await api.apiFetch("/auth/refresh", { method: "POST", headers: { Authorization: "Bearer unit-test-token" } })
  assert.equal(calls[0].init.headers.get("Authorization"), "Bearer unit-test-token")
})
