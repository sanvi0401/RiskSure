const DEFAULT_API_BASE_URL = ""

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || DEFAULT_API_BASE_URL

export const API_ENDPOINTS = {
  applications: `${API_BASE_URL}/applications`,
  health: `${API_BASE_URL}/health`,
  process: `${API_BASE_URL}/process`,
  save: `${API_BASE_URL}/save`,
}

export async function apiFetch(path: string, init: RequestInit = {}) {
  const token = typeof window !== "undefined"
    ? window.localStorage.getItem("risksure_access_token")
    : null

  const headers = new Headers(init.headers)
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json")
  }
  if (token) headers.set("Authorization", `Bearer ${token}`)

  const response = await fetch(`${API_BASE_URL}${path.startsWith("/") ? path : `/${path}`}`, {
    ...init,
    headers,
  })

  if (response.status === 401 && typeof window !== "undefined") {
    window.localStorage.removeItem("risksure_access_token")
    window.localStorage.removeItem("risksure_user")
  }

  return response
}
