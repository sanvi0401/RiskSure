const DEFAULT_API_BASE_URL = "https://risk-sure.vercel.app"

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || DEFAULT_API_BASE_URL

export const API_ENDPOINTS = {
  applications: "/applications",
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
  policies: "/policies",
  policyIntelligence: (id: number) => `/policies/${id}/intelligence`,
  policyDocument: (id: number) => `/policies/${id}/document`,
  fraud: (id: number) => `/fraud/investigation/${id}`,
  billing: "/billing",
  customerPortal: "/customer/portal",
  caseIntelligence: (id: number) => `/cases/${id}/intelligence`,
  claimIntelligence: (id: number) => `/claims/${id}/intelligence`,
  claimGraph: (id: number) => `/graph/claim/${id}`,
}

export async function apiFetch(path: string, init: RequestInit = {}) {
  const token =
    typeof window !== "undefined"
      ? localStorage.getItem("risksure_access_token")
      : null

  const headers = new Headers(init.headers)
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`)
  }

  const response = await fetch(
    `${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`,
    { ...init, headers, cache: "no-store" },
  )

  if (response.status === 401 && typeof window !== "undefined") {
    localStorage.removeItem("risksure_access_token")
    localStorage.removeItem("risksure_user")
  }

  return response
}

export async function apiJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await apiFetch(path, init)
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const message =
      data && typeof data === "object" && "error" in data
        ? String((data as { error: unknown }).error)
        : `Request failed with status ${response.status}`
    throw new Error(message)
  }
  return data as T
}
