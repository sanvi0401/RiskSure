const DEFAULT_API_BASE_URL = "http://localhost:5000"

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || DEFAULT_API_BASE_URL

export const API_ENDPOINTS = {
  applications: `${API_BASE_URL}/applications`,
  health: `${API_BASE_URL}/health`,
  process: `${API_BASE_URL}/process`,
  save: `${API_BASE_URL}/save`,
}
