"use client"

import { createContext, useContext, useEffect, useState, ReactNode } from "react"
import { API_BASE_URL } from "@/lib/api"

export type UserRole = "customer" | "underwriter" | "claims_officer" | "provider" | "admin"

export interface AuthUser {
  id: number
  email: string
  role: UserRole
  created_at?: string | null
}

interface AuthContextType {
  user: AuthUser | null
  token: string | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<{ type: "complete" | "totp" | "setup"; user: AuthUser; challenge?: string; setupToken?: string }>\n  verifyTotp: (challenge: string, code: string) => Promise<void>\n  verifyTotpSetup: (setupToken: string, code: string) => Promise<string[]>
  logout: () => void
  hasRole: (roles: UserRole | UserRole[]) => boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    const storedToken = window.localStorage.getItem("risksure_access_token")
    const storedUser = window.localStorage.getItem("risksure_user")
    if (storedToken && storedUser) {
      try {
        setToken(storedToken)
        setUser(JSON.parse(storedUser))
      } catch {
        window.localStorage.removeItem("risksure_access_token")
        window.localStorage.removeItem("risksure_user")
      }
    }
    setIsLoading(false)
  }, [])

  const storeSession = (accessToken: string, nextUser: AuthUser) => {
    setToken(accessToken)
    setUser(nextUser)
    window.localStorage.setItem("risksure_access_token", accessToken)
    window.localStorage.setItem("risksure_user", JSON.stringify(nextUser))
  }

  const login = async (email: string, password: string) => {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.error || "Login failed")

    if (data.totp_setup_required) return { type: "setup" as const, user: data.user, setupToken: data.setup_token }
    if (data.requires_totp) return { type: "totp" as const, user: data.user, challenge: String(data.user_id) }
    storeSession(data.access_token, data.user)
    return { type: "complete" as const, user: data.user }
  }

  const verifyTotp = async (challenge: string, code: string) => {
    const response = await fetch(`${API_BASE_URL}/auth/login/verify-totp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: Number(challenge), code }),
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.error || "Invalid authenticator code")
    storeSession(data.access_token, data.user)
  }

  const verifyTotpSetup = async (setupToken: string, code: string) => {
    const response = await fetch(`${API_BASE_URL}/auth/totp/verify-setup`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${setupToken}` },
      body: JSON.stringify({ code }),
    })
    const data = await response.json()
    if (!response.ok) throw new Error(data.error || "Invalid authenticator code")
    storeSession(data.access_token, data.user)
    return data.recovery_codes as string[]
  }
