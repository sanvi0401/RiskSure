import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import test from "node:test"
import { runInNewContext } from "node:vm"
import ts from "typescript"

const source = readFileSync(new URL("../context/auth-context.tsx", import.meta.url), "utf8")
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText

function harness(respond) {
  const exports = {}
  const states = []
  const effects = []
  const calls = []
  const routes = []
  const storage = {
    risksure_access_token: "unit-access",
    risksure_refresh_token: "unit-refresh",
    risksure_user: '{"id":7,"email":"staff@example.invalid","role":"underwriter"}',
  }
  let sessionCleared = false
  runInNewContext(compiled, {
    exports, window: {},
    localStorage: {
      getItem: key => storage[key] ?? null,
      setItem: (key, value) => { storage[key] = value },
      removeItem: key => { delete storage[key] },
    },
    sessionStorage: { clear: () => { sessionCleared = true } },
    require: name => {
      if (name === "react/jsx-runtime") return { jsx: (_, props) => ({ props }) }
      if (name === "react") return {
        createContext: () => ({ Provider: {} }),
        useRef: value => ({ current: value }),
        useEffect: callback => effects.push(callback),
        useState: value => {
          const index = states.length
          states.push(value)
          return [value, next => { states[index] = next }]
        },
      }
      if (name === "next/navigation") return { useRouter: () => ({ replace: path => routes.push(path) }) }
      if (name === "@/lib/api") return { apiFetch: (url, init) => {
        calls.push({ url, init })
        return respond(url, init)
      } }
      throw new Error("Unexpected test import")
    },
  })
  const auth = exports.AuthProvider({ children: null }).props.value
  return { auth, storage, states, effects, calls, routes, sessionCleared: () => sessionCleared }
}

test("logout clears local data and navigates to Thank you before server acknowledgment", async () => {
  let finish
  const h = harness(() => new Promise(resolve => { finish = () => resolve(new Response("{}")) }))
  const pending = h.auth.logout()
  assert.deepEqual(h.storage, {})
  assert.equal(h.sessionCleared(), true)
  assert.deepEqual(h.routes, ["/signed-out"])
  assert.equal(h.states[0], true)
  assert.equal(h.states[2], true)
  assert.equal(h.calls[0].url, "/auth/logout")
  assert.equal(h.calls[0].init.headers.Authorization, "Bearer unit-access")
  assert.equal(h.calls[0].init.keepalive, true)
  finish()
  await pending
  assert.equal(h.states[0], false)
  assert.equal(h.states[1], "")
  assert.equal(h.states[2], true)
})

test("server failure does not undo sign-out or hide the honest confirmation warning", async () => {
  const h = harness(async () => { throw new Error("Offline") })
  await h.auth.logout()
  assert.deepEqual(h.storage, {})
  assert.deepEqual(h.routes, ["/signed-out"])
  assert.match(h.states[1], /signed out on this device.*Server confirmation is unavailable/)
  assert.equal(h.states[0], false)
})

test("a pending session restoration cannot resurrect a signed-out user", async () => {
  let finishRestore
  const h = harness(url => url === "/auth/me"
    ? new Promise(resolve => { finishRestore = () => resolve(new Response('{"user":{"id":7,"role":"underwriter"}}')) })
    : Promise.resolve(new Response("{}")))
  h.effects[0]()
  await h.auth.logout()
  finishRestore()
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(h.storage, {})
  assert.equal(h.states[3], null)
  assert.equal(h.states[4], null)
  assert.deepEqual(h.routes, ["/signed-out"])
})
