// Same-domain Vercel deployments expose the Flask adapter under /api.
// Set NEXT_PUBLIC_API_BASE_URL for a separately deployed backend.
const DEFAULT_API_BASE_URL = "/api"

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || DEFAULT_API_BASE_URL

export const API_ENDPOINTS = {
  applications: "/applications",
  application: (id: number) => `/applications/${id}`,
  health: "/health",
  process: "/process",
  save: "/save",
  underwritingQueue: "/underwriting/queue",
  underwritingAssign: (id: number) => `/underwriting/applications/${id}/assign`,
  underwritingDecision: (id: number) => `/underwriting/applications/${id}/decision`,
  claims: "/claims",
  claim: (id: number) => `/claims/${id}`,
  provider: "/providers/me",
  providerClaims: "/providers/me/claims",
  adminUsers: "/admin/users",
  adminOverview: "/admin/overview",
  adminAudit: "/admin/audit-logs",
  adminRole: (id: number) => `/admin/users/${id}/role`,
  adminGraph: "/admin/graph",
  policies: "/policies",
  policyIntelligence: (id: number) => `/policies/${id}/intelligence`,
  policyDocument: (id: number) => `/policies/${id}/document`,
  fraud: (id: number) => `/fraud/investigation/${id}`,
  billing: "/billing",
  customerPortal: "/customer/portal",
  caseIntelligence: (id: number) => `/cases/${id}/intelligence`,
  caseAssistant: (id: number) => `/cases/${id}/assistant`,
  riskAnalysis: (id: number) => `/applications/${id}/risk-analysis`,
  claimIntelligence: (id: number) => `/claims/${id}/intelligence`,
  claimGraph: (id: number) => `/graph/claim/${id}`,
  relationshipGraph: "/graph",
}

type ApiRequestInit = RequestInit & { timeoutMs?: number }

export async function apiFetch(path: string, init: ApiRequestInit = {}) {
  const { timeoutMs = 30_000, ...requestInit } = init
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("risksure_access_token")
      : null

  const headers = new Headers(requestInit.headers)
  if (requestInit.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }
  // Respect an explicit Authorization header (TOTP challenge/setup and refresh tokens).
  if (token && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${token}`)
  }

  const controller = new AbortController()
  const abortFromCaller = () => controller.abort()
  requestInit.signal?.addEventListener("abort", abortFromCaller, { once: true })
  if (requestInit.signal?.aborted) controller.abort()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(
      `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`,
      { ...requestInit, headers, cache: "no-store", signal: controller.signal },
    )

    const usedStoredToken = !new Headers(requestInit.headers).has("Authorization")
    if (response.status === 401 && usedStoredToken && typeof window !== "undefined" && !path.includes("/auth/")) {
      const refresh = localStorage.getItem("risksure_refresh_token")
      if (refresh) {
        try {
          const refreshResponse = await fetch(`${API_BASE_URL}/auth/refresh`, {
            method: "POST",
            headers: { Authorization: "Bearer " + refresh },
            cache: "no-store",
            signal: controller.signal,
          })
          const refreshData = await refreshResponse.json().catch(() => null)
          if (refreshResponse.ok && refreshData?.access_token) {
            localStorage.setItem("risksure_access_token", refreshData.access_token)
            const retryHeaders = new Headers(requestInit.headers)
            if (requestInit.body && !retryHeaders.has("Content-Type")) retryHeaders.set("Content-Type", "application/json")
            retryHeaders.set("Authorization", "Bearer " + refreshData.access_token)
            return await fetch(`${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`, {
              ...requestInit, headers: retryHeaders, cache: "no-store", signal: controller.signal,
            })
          }
        } catch (error) {
          if (controller.signal.aborted) throw error
          // Fall through to normal session cleanup.
        }
      }
      localStorage.removeItem("risksure_access_token")
      localStorage.removeItem("risksure_refresh_token")
      localStorage.removeItem("risksure_user")
      try { sessionStorage.clear() } catch {}
      if (typeof window !== "undefined") {
        const current = window.location.pathname + window.location.search
        const safeNext = current.startsWith("/") && !current.startsWith("//") && !current.includes("\\") ? current : "/dashboard"
        window.location.assign("/login?session_expired=1&next=" + encodeURIComponent(safeNext))
      }
    }

    return response
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("The request timed out. Please try again.")
    }
    if (error instanceof TypeError) {
      throw new Error("Unable to reach the RiskSure backend. Check your connection and try again.")
    }
    throw error
  } finally {
    clearTimeout(timeoutId)
    requestInit.signal?.removeEventListener("abort", abortFromCaller)
  }
}

export async function apiJson<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const response = await apiFetch(path, init)
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const message =
      data && typeof data === "object" && "error" in data
        ? String((data as { error: unknown }).error)
        : `Request failed with status ${response.status}`
    throw new Error(message)
  }
  if (data === null) {
    throw new Error("The backend returned an empty or invalid response.")
  }
  return data as T
}
