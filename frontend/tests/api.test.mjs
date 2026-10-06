import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"
import { runInNewContext } from "node:vm"
import ts from "typescript"

const source = readFileSync(new URL("../lib/api.ts", import.meta.url), "utf8")
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText

function harness(options = {}) {
  const calls = []
  const timers = []
  const callbacks = []
  const cleared = []
  const exports = {}
  runInNewContext(compiled, {
    exports, process: { env: {} }, Headers, AbortController, DOMException,
    ...(options.storage ? { window: {}, localStorage: {
      getItem: (key) => options.storage[key],
      setItem: (key, value) => { options.storage[key] = value },
    } } : {}),
    fetch: async (url, init) => {
      calls.push({ url, init })
      if (options.respond) return options.respond(calls.length, init)
      return new Response('{"verified":true}', { headers: { "Content-Type": "application/json" } })
    },
    setTimeout: (callback, milliseconds) => { callbacks.push(callback); timers.push(milliseconds); return timers.length },
    clearTimeout: (id) => cleared.push(id),
  })
  return { api: exports, calls, timers, cleared, callbacks }
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

test("a caller signal does not bypass the request deadline", async () => {
  const { api, calls, callbacks } = harness()
  const caller = new AbortController()
  await api.apiFetch("/policies", { signal: caller.signal })
  callbacks[0]()
  assert.equal(calls[0].init.signal.aborted, true)
  assert.equal(caller.signal.aborted, false)
})

test("an already cancelled caller aborts the combined signal", async () => {
  const { api, calls } = harness()
  const caller = new AbortController()
  caller.abort()
  await api.apiFetch("/billing", { signal: caller.signal })
  assert.equal(calls[0].init.signal.aborted, true)
})

test("caller cancellation reaches an in-flight request", async () => {
  const { api, calls } = harness()
  const caller = new AbortController()
  const pending = api.apiFetch("/policies", { signal: caller.signal })
  caller.abort()
  await pending
  assert.equal(calls[0].init.signal.aborted, true)
})

test("refresh and retry remain bounded until the retry finishes", async () => {
  let finish
  const { api, calls, cleared } = harness({
    storage: { risksure_access_token: "unit-expired", risksure_refresh_token: "unit-refresh" },
    respond: (number) => {
      if (number === 1) return new Response("{}", { status: 401 })
      if (number === 2) return new Response('{"access_token":"unit-refreshed"}')
      return new Promise(resolve => { finish = () => resolve(new Response("{}")) })
    },
  })
  const pending = api.apiFetch("/policies")
  while (calls.length < 3) await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(cleared, [])
  assert.equal(calls[0].init.signal, calls[1].init.signal)
  assert.equal(calls[0].init.signal, calls[2].init.signal)
  assert.equal(calls[2].init.headers.get("Authorization"), "Bearer unit-refreshed")
  finish()
  await pending
  assert.deepEqual(cleared, [1])
})

test("a stale 401 after logout cannot refresh or redirect the session", async () => {
  const storage = { risksure_access_token: "unit-expired", risksure_refresh_token: "unit-refresh" }
  let finish
  const { api, calls } = harness({
    storage,
    respond: () => new Promise(resolve => { finish = () => resolve(new Response("{}", { status: 401 })) }),
  })
  const pending = api.apiFetch("/policies")
  delete storage.risksure_access_token
  delete storage.risksure_refresh_token
  finish()
  assert.equal((await pending).status, 401)
  assert.equal(calls.length, 1)
  assert.deepEqual(storage, {})
})

test("a refresh already in flight cannot restore tokens after logout", async () => {
  const storage = { risksure_access_token: "unit-expired", risksure_refresh_token: "unit-refresh" }
  let finish
  const { api, calls } = harness({
    storage,
    respond: (number) => number === 1
      ? new Response("{}", { status: 401 })
      : new Promise(resolve => { finish = () => resolve(new Response('{"access_token":"unit-refreshed"}')) }),
  })
  const pending = api.apiFetch("/policies")
  while (calls.length < 2) await new Promise(resolve => setImmediate(resolve))
  delete storage.risksure_access_token
  delete storage.risksure_refresh_token
  finish()
  assert.equal((await pending).status, 401)
  assert.equal(calls.length, 2)
  assert.deepEqual(storage, {})
})

test("a refresh network failure after logout cannot redirect away from Thank you", async () => {
  const storage = { risksure_access_token: "unit-expired", risksure_refresh_token: "unit-refresh" }
  let fail
  const { api, calls } = harness({
    storage,
    respond: (number) => number === 1
      ? new Response("{}", { status: 401 })
      : new Promise((_, reject) => { fail = () => reject(new TypeError("Offline")) }),
  })
  const pending = api.apiFetch("/policies")
  while (calls.length < 2) await new Promise(resolve => setImmediate(resolve))
  delete storage.risksure_access_token
  delete storage.risksure_refresh_token
  fail()
  assert.equal((await pending).status, 401)
  assert.deepEqual(storage, {})
})
